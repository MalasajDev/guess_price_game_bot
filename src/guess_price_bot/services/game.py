import asyncio
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from guess_price_bot.db.models import GameSession, Round, User, WhoCloserParticipant
from guess_price_bot.db.repositories import (
    GameSessionRepository,
    NewRound,
    RoundRepository,
    UserRepository,
    WhoCloserRepository,
)
from guess_price_bot.domain.models import Category, Currency, GameMode
from guess_price_bot.domain.scoring import (
    evaluate_comparison,
    evaluate_guess,
    make_threshold,
    parse_guess,
)
from guess_price_bot.providers.contracts import ListingProvider, RateSnapshot, Translator

logger = structlog.get_logger(__name__)


class RateProvider(Protocol):
    async def fetch(self) -> RateSnapshot: ...


class RateCache:
    def __init__(self, provider: RateProvider, ttl: timedelta = timedelta(hours=1)) -> None:
        self.provider = provider
        self.ttl = ttl
        self._snapshot: RateSnapshot | None = None
        self._lock = asyncio.Lock()

    async def get(self, *, force: bool = False) -> RateSnapshot:
        now = datetime.now(UTC)
        if not force and self._snapshot is not None and now - self._snapshot.fetched_at < self.ttl:
            return self._snapshot
        async with self._lock:
            now = datetime.now(UTC)
            if force or self._snapshot is None or now - self._snapshot.fetched_at >= self.ttl:
                self._snapshot = await self.provider.fetch()
                logger.info("exchange_rates_refreshed", provider_at=self._snapshot.provider_at)
            return self._snapshot


@dataclass(frozen=True, slots=True)
class RoundView:
    id: str
    mode: GameMode
    title: str
    description: str
    image_url: str
    source_url: str
    displayed_price: Decimal
    currency: Currency
    threshold: Decimal | None


@dataclass(frozen=True, slots=True)
class AnswerView:
    correct: bool
    actual_price: Decimal
    currency: Currency
    awarded_points: int
    already_resolved: bool
    round_continues: bool = False


@dataclass(frozen=True, slots=True)
class WhoCloserResult:
    actual_price: Decimal
    currency: Currency
    winner_name: str | None
    answers: list[tuple[str, Decimal | None]]


class GameService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        providers: dict[Category, ListingProvider],
        translator: Translator,
        rates: RateCache,
        rng: random.Random | None = None,
    ) -> None:
        self.session = session
        self.providers = providers
        self.translator = translator
        self.rates = rates
        self.rng = rng or random.SystemRandom()
        self.users = UserRepository(session)
        self.games = GameSessionRepository(session)
        self.rounds = RoundRepository(session)
        self.who_closer = WhoCloserRepository(session)

    async def start(
        self,
        telegram_id: int,
        display_name: str,
        mode: GameMode,
        *,
        chat_id: int | None = None,
    ) -> str:
        user = await self.users.get_or_create(telegram_id, display_name)
        scope_id = telegram_id if chat_id is None else chat_id
        active = await self.games.get_active_for_chat(scope_id)
        if active is not None and active.user_id != user.id:
            raise PermissionError("only the game owner may replace the game")
        await self.users.register_in_chat(scope_id, user.id)
        game = await self.games.start(user.id, mode, chat_id=scope_id)
        await self.session.commit()
        logger.info("game_started", telegram_id=telegram_id, mode=mode.value)
        return game.id

    async def select_category(
        self, telegram_id: int, category: Category, *, chat_id: int | None = None
    ) -> None:
        game = await self._active_game(telegram_id, chat_id)
        if await self.rounds.latest_pending(game.id) is not None:
            raise ValueError("finish the current round first")
        if category is Category.RANDOM:
            category = self.rng.choice(Category.playable())
        await self.games.set_category(game.id, category)
        await self.session.commit()

    async def select_currency(
        self, telegram_id: int, currency: Currency, *, chat_id: int | None = None
    ) -> RoundView:
        game = await self._active_game(telegram_id, chat_id)
        if game.category is None:
            raise LookupError("category is not selected")
        if await self.rounds.latest_pending(game.id) is not None:
            raise ValueError("finish the current round first")
        await self.games.set_currency(game.id, currency)
        await self.session.flush()
        view = await self._create_round(game)
        await self.session.commit()
        return view

    async def next_round(self, telegram_id: int, *, chat_id: int | None = None) -> RoundView:
        game = await self._active_game(telegram_id, chat_id)
        if game.category is None or game.currency is None:
            raise LookupError("game is not configured")
        if await self.rounds.latest_pending(game.id) is not None:
            raise ValueError("finish the current round first")
        view = await self._create_round(game)
        await self.session.commit()
        return view

    async def answer_guess(
        self,
        telegram_id: int,
        text: str,
        *,
        chat_id: int | None = None,
        display_name: str = "Игрок",
        reply_to_message_id: int | None = None,
    ) -> AnswerView:
        game, round_ = await self._active_round(telegram_id, chat_id, require_owner=False)
        if GameMode(game.mode) is not GameMode.GUESS:
            raise ValueError("active game does not accept a price guess")
        if game.chat_id != telegram_id and round_.card_message_id != reply_to_message_id:
            raise LookupError("group guess must reply to card")
        guess = parse_guess(text)
        result = evaluate_guess(round_.displayed_price, guess, Category(game.category))
        user = await self.users.get_or_create(telegram_id, display_name)
        await self.users.register_in_chat(game.chat_id, user.id)
        if game.chat_id != telegram_id and not result.correct:
            await self.session.commit()
            return AnswerView(
                correct=False,
                actual_price=round_.displayed_price,
                currency=Currency(round_.displayed_currency),
                awarded_points=0,
                already_resolved=False,
                round_continues=True,
            )
        return await self._resolve(round_, result.correct, str(guess), scorer_user_id=user.id)

    async def answer_comparison(
        self,
        telegram_id: int,
        direction: str,
        *,
        chat_id: int | None = None,
        display_name: str = "Игрок",
    ) -> AnswerView:
        game, round_ = await self._active_round(telegram_id, chat_id)
        if GameMode(game.mode) is not GameMode.MORE_LESS or round_.threshold is None:
            raise ValueError("active game does not accept a comparison")
        user = await self.users.get_or_create(telegram_id, display_name)
        await self.users.register_in_chat(game.chat_id, user.id)
        if game.user_id != user.id:
            raise PermissionError("only the game owner may answer")
        result = evaluate_comparison(round_.displayed_price, direction, round_.threshold)
        return await self._resolve(round_, result.correct, direction, scorer_user_id=user.id)

    async def stop(self, telegram_id: int, *, chat_id: int | None = None) -> None:
        game = await self._active_game(telegram_id, chat_id)
        await self.games.stop(game.id)
        await self.session.commit()

    async def skip_personal_round(self, telegram_id: int) -> AnswerView:
        game, round_ = await self._active_round(telegram_id)
        if game.chat_id != telegram_id:
            raise PermissionError("group games require a vote")
        return await self._resolve(round_, False, "skipped")

    async def skip_group_round(self, chat_id: int) -> AnswerView:
        game = await self.games.get_active_for_chat(chat_id)
        if game is None:
            raise LookupError("group game not found")
        round_ = await self.rounds.latest_pending(game.id)
        if round_ is None:
            raise LookupError("round not found")
        return await self._resolve(round_, False, "skipped")

    async def mark_private_chat(self, telegram_id: int, display_name: str) -> None:
        await self.users.mark_private_chat(telegram_id, display_name)
        await self.session.commit()

    async def set_card_message_id(self, round_id: str, message_id: int) -> None:
        await self.rounds.set_card_message_id(round_id, message_id)
        await self.session.commit()

    async def start_who_closer(self, telegram_id: int, display_name: str, chat_id: int) -> str:
        game_id = await self.start(telegram_id, display_name, GameMode.WHO_CLOSER, chat_id=chat_id)
        game = await self.games.require(game_id)
        game.status = "registration"
        game.registration_deadline = datetime.now(UTC) + timedelta(minutes=1)
        await self.session.commit()
        return game_id

    async def join_who_closer(self, telegram_id: int, display_name: str, chat_id: int) -> bool:
        game = await self._active_game(telegram_id, chat_id, require_owner=False)
        if GameMode(game.mode) is not GameMode.WHO_CLOSER or game.status != "registration":
            raise LookupError("registration is closed")
        user = await self.users.by_telegram_id(telegram_id)
        if user is None or not user.has_private_chat:
            raise PermissionError("private chat is required")
        user.display_name = display_name
        joined = await self.who_closer.join(game.id, user.id)
        await self.session.commit()
        return joined

    async def add_who_closer_time(self, telegram_id: int, chat_id: int) -> bool:
        game = await self._active_game(telegram_id, chat_id, require_owner=False)
        if GameMode(game.mode) is not GameMode.WHO_CLOSER or game.status != "registration":
            raise LookupError("registration is closed")
        user = await self.users.by_telegram_id(telegram_id)
        if user is None or not await self.who_closer.extend_once(game.id, user.id):
            return False
        game.registration_deadline = (game.registration_deadline or datetime.now(UTC)) + timedelta(
            seconds=30
        )
        await self.session.commit()
        return True

    async def activate_who_closer(self, chat_id: int) -> tuple[int, str] | None:
        game = await self.games.get_active_for_chat(chat_id)
        if game is None or GameMode(game.mode) is not GameMode.WHO_CLOSER:
            return None
        if game.status != "registration" or game.registration_deadline is None:
            return None
        if game.registration_deadline > datetime.now(UTC):
            return None
        game.status = "active"
        owner = await self.session.get(User, game.user_id)
        await self.session.commit()
        return None if owner is None else (owner.telegram_id, owner.display_name)

    async def open_who_closer_round(self, chat_id: int, owner_id: int) -> list[tuple[int, str]]:
        game = await self._active_game(owner_id, chat_id)
        if GameMode(game.mode) is not GameMode.WHO_CLOSER:
            raise ValueError("wrong mode")
        game.status = "active"
        game.answer_deadline = datetime.now(UTC) + timedelta(seconds=90)
        users = await self.who_closer.participant_users(game.id)
        await self.session.commit()
        return users

    async def submit_who_closer_answer(self, telegram_id: int, text: str, chat_id: int) -> bool:
        game, round_ = await self._active_round(telegram_id, chat_id, require_owner=False)
        if (
            GameMode(game.mode) is not GameMode.WHO_CLOSER
            or game.answer_deadline is None
            or game.answer_deadline < datetime.now(UTC)
        ):
            raise LookupError("answer window closed")
        user = await self.users.by_telegram_id(telegram_id)
        if user is None:
            raise PermissionError("not registered")
        accepted = await self.who_closer.submit(round_.id, user.id, parse_guess(text))
        await self.session.commit()
        return accepted

    async def submit_who_closer_private_answer(self, telegram_id: int, text: str) -> bool | None:
        user = await self.users.by_telegram_id(telegram_id)
        if user is None:
            return None
        game = await self.session.scalar(
            select(GameSession)
            .join(WhoCloserParticipant, WhoCloserParticipant.session_id == GameSession.id)
            .where(
                WhoCloserParticipant.user_id == user.id,
                GameSession.mode == GameMode.WHO_CLOSER.value,
                GameSession.status == "active",
            )
            .order_by(GameSession.created_at.desc())
            .limit(1)
        )
        if game is None:
            return None
        return await self.submit_who_closer_answer(telegram_id, text, game.chat_id)

    async def finish_who_closer_round(self, chat_id: int) -> WhoCloserResult | None:
        game = await self.games.get_active_for_chat(chat_id)
        if game is None or GameMode(game.mode) is not GameMode.WHO_CLOSER:
            return None
        round_ = await self.rounds.latest_pending(game.id)
        if round_ is None:
            return None
        answers = await self.who_closer.answers(round_.id)
        participants = await self.who_closer.participants(game.id)
        users = {
            participant.user_id: await self.session.get(User, participant.user_id)
            for participant in participants
        }
        winner = min(
            answers,
            key=lambda answer: (abs(answer.price - round_.displayed_price), answer.submitted_at),
            default=None,
        )
        if winner is not None:
            await self._resolve(round_, True, str(winner.price), scorer_user_id=winner.user_id)
        else:
            await self._resolve(round_, False, "no answer")
        values = {answer.user_id: answer.price for answer in answers}
        return WhoCloserResult(
            actual_price=round_.displayed_price,
            currency=Currency(round_.displayed_currency),
            winner_name=None
            if winner is None or users[winner.user_id] is None
            else users[winner.user_id].display_name,
            answers=[
                (user.display_name, values.get(user_id))
                for user_id, user in users.items()
                if user is not None
            ],
        )

    async def score(self, telegram_id: int) -> int:
        user = await self.users.by_telegram_id(telegram_id)
        return 0 if user is None else await self.users.score_for(user.id)

    async def rating(self, chat_id: int) -> list[tuple[str, int]]:
        return await self.users.rating_for_chat(chat_id)

    async def register_member(self, chat_id: int, telegram_id: int, display_name: str) -> None:
        user = await self.users.get_or_create(telegram_id, display_name)
        await self.users.register_in_chat(chat_id, user.id)
        await self.session.commit()

    async def score_in_chat(self, chat_id: int, telegram_id: int, display_name: str) -> int:
        user = await self.users.get_or_create(telegram_id, display_name)
        await self.users.register_in_chat(chat_id, user.id)
        await self.session.commit()
        return user.score

    async def _active_game(
        self, telegram_id: int, chat_id: int | None = None, *, require_owner: bool = True
    ) -> GameSession:
        if chat_id is not None:
            game = await self.games.get_active_for_chat(chat_id)
            if game is None:
                raise LookupError("active game not found")
            user = await self.users.by_telegram_id(telegram_id)
            if require_owner and (user is None or game.user_id != user.id):
                raise PermissionError("only the game owner may change the game")
            return game
        user = await self.users.by_telegram_id(telegram_id)
        if user is None:
            raise LookupError("user not found")
        game = await self.games.get_active_for_user(user.id)
        if game is None:
            raise LookupError("active game not found")
        return game

    async def _active_round(
        self, telegram_id: int, chat_id: int | None = None, *, require_owner: bool = True
    ) -> tuple[GameSession, Round]:
        game = await self._active_game(telegram_id, chat_id, require_owner=require_owner)
        round_ = await self.rounds.latest_pending(game.id) or await self.rounds.latest(game.id)
        if round_ is None:
            raise LookupError("round not found")
        return game, round_

    async def _create_round(self, game: GameSession) -> RoundView:
        started_at = time.perf_counter()
        category = Category(game.category)
        currency = Currency(game.currency)
        external_started_at = time.perf_counter()
        card, snapshot = await asyncio.gather(
            self.providers[category].get_card(),
            self.rates.get(),
        )
        external_ms = (time.perf_counter() - external_started_at) * 1000
        translation_started_at = time.perf_counter()
        translated = await self.translator.translate_card(card.title, card.description)
        translation_ms = (time.perf_counter() - translation_started_at) * 1000
        displayed = snapshot.convert(card.price, card.currency, currency.value)
        threshold = (
            make_threshold(displayed, self.rng)
            if GameMode(game.mode) is GameMode.MORE_LESS
            else None
        )
        round_ = await self.rounds.create_pending(
            game.id,
            NewRound(
                provider=card.source,
                source_listing_id=card.source_id,
                source_url=card.source_url,
                image_url=card.image_url,
                source_title=card.title,
                source_description=card.description,
                translated_title=translated.title,
                translated_description=translated.description,
                source_price=card.price,
                source_currency=card.currency,
                conversion_rate=displayed / card.price,
                displayed_price=displayed,
                displayed_currency=currency,
                provider_observed_at=card.observed_at,
                rate_observed_at=snapshot.provider_at,
                threshold=threshold,
            ),
        )
        logger.info(
            "round_created",
            session_id=game.id,
            category=category.value,
            external_ms=round(external_ms, 1),
            translation_ms=round(translation_ms, 1),
            total_ms=round((time.perf_counter() - started_at) * 1000, 1),
        )
        return self._round_view(game, round_)

    async def _resolve(
        self,
        round_: Round,
        correct: bool,
        answer: str,
        *,
        scorer_user_id: str | None = None,
    ) -> AnswerView:
        outcome = await self.rounds.resolve(
            round_.id,
            correct=correct,
            answer=answer,
            scorer_user_id=scorer_user_id,
        )
        await self.session.commit()
        logger.info("round_resolved", round_id=round_.id, correct=correct)
        return AnswerView(
            correct=bool(round_.correct) if outcome.already_resolved else correct,
            actual_price=round_.displayed_price,
            currency=Currency(round_.displayed_currency),
            awarded_points=outcome.awarded_points,
            already_resolved=outcome.already_resolved,
        )

    @staticmethod
    def _round_view(game: GameSession, round_: Round) -> RoundView:
        return RoundView(
            id=round_.id,
            mode=GameMode(game.mode),
            title=round_.translated_title,
            description=round_.translated_description,
            image_url=round_.image_url,
            source_url=round_.source_url,
            displayed_price=round_.displayed_price,
            currency=Currency(round_.displayed_currency),
            threshold=round_.threshold,
        )
