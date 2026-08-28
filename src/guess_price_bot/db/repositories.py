from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from guess_price_bot.db.models import (
    GameSession,
    GroupMember,
    Round,
    User,
    WhoCloserAnswer,
    WhoCloserParticipant,
)
from guess_price_bot.domain.models import Category, Currency, GameMode


@dataclass(frozen=True, slots=True)
class NewRound:
    provider: str
    source_listing_id: str
    source_url: str
    image_url: str
    source_title: str
    source_description: str
    translated_title: str
    translated_description: str
    source_price: Decimal
    source_currency: str
    conversion_rate: Decimal
    displayed_price: Decimal
    displayed_currency: Currency
    provider_observed_at: datetime
    rate_observed_at: datetime
    threshold: Decimal | None


@dataclass(frozen=True, slots=True)
class ResolveResult:
    awarded_points: int
    already_resolved: bool


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, telegram_id: int, display_name: str) -> User:
        user = await self.session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            user = User(telegram_id=telegram_id, display_name=display_name)
            self.session.add(user)
        else:
            user.display_name = display_name
        await self.session.flush()
        return user

    async def by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.telegram_id == telegram_id))

    async def mark_private_chat(self, telegram_id: int, display_name: str) -> User:
        user = await self.get_or_create(telegram_id, display_name)
        user.has_private_chat = True
        await self.session.flush()
        return user

    async def score_for(self, user_id: str) -> int:
        user = await self.session.get(User, user_id)
        return 0 if user is None else user.score

    async def register_in_chat(self, chat_id: int, user_id: str) -> None:
        member = await self.session.scalar(
            select(GroupMember).where(
                GroupMember.chat_id == chat_id, GroupMember.user_id == user_id
            )
        )
        if member is None:
            self.session.add(GroupMember(chat_id=chat_id, user_id=user_id))
            await self.session.flush()

    async def rating_for_chat(self, chat_id: int) -> list[tuple[str, int]]:
        rows = await self.session.execute(
            select(User.display_name, User.score)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.chat_id == chat_id)
            .order_by(User.score.desc(), User.display_name.asc())
        )
        return [(name, score) for name, score in rows.all()]


class GameSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start(
        self, user_id: str, mode: GameMode, *, chat_id: int | None = None
    ) -> GameSession:
        if chat_id is None:
            user = await self.session.get(User, user_id)
            if user is None:
                raise LookupError("user not found")
            chat_id = user.telegram_id
        active = await self.get_active_for_chat(chat_id)
        if active is not None:
            active.status = "stopped"
        game = GameSession(user_id=user_id, chat_id=chat_id, mode=mode.value, status="active")
        self.session.add(game)
        await self.session.flush()
        return game

    async def configure(
        self, session_id: str, category: Category, currency: Currency
    ) -> GameSession:
        game = await self.require(session_id)
        game.category = category.value
        game.currency = currency.value
        await self.session.flush()
        return game

    async def set_category(self, session_id: str, category: Category) -> GameSession:
        game = await self.require(session_id)
        game.category = category.value
        await self.session.flush()
        return game

    async def set_currency(self, session_id: str, currency: Currency) -> GameSession:
        game = await self.require(session_id)
        game.currency = currency.value
        await self.session.flush()
        return game

    async def get(self, session_id: str) -> GameSession | None:
        return await self.session.get(GameSession, session_id)

    async def require(self, session_id: str) -> GameSession:
        game = await self.get(session_id)
        if game is None:
            raise LookupError("game session not found")
        return game

    async def get_active_for_user(self, user_id: str) -> GameSession | None:
        return await self.session.scalar(
            select(GameSession).where(
                GameSession.user_id == user_id, GameSession.status == "active"
            )
        )

    async def get_active_for_chat(self, chat_id: int) -> GameSession | None:
        return await self.session.scalar(
            select(GameSession).where(
                GameSession.chat_id == chat_id, GameSession.status.in_(("active", "registration"))
            )
        )

    async def set_status(self, session_id: str, status: str) -> GameSession:
        game = await self.require(session_id)
        game.status = status
        await self.session.flush()
        return game

    async def stop(self, session_id: str) -> None:
        game = await self.require(session_id)
        game.status = "stopped"
        await self.session.flush()


class RoundRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_pending(self, session_id: str, data: NewRound) -> Round:
        round_ = Round(
            session_id=session_id,
            provider=data.provider,
            source_listing_id=data.source_listing_id,
            source_url=data.source_url,
            image_url=data.image_url,
            source_title=data.source_title,
            source_description=data.source_description,
            translated_title=data.translated_title,
            translated_description=data.translated_description,
            source_price=data.source_price,
            source_currency=data.source_currency,
            conversion_rate=data.conversion_rate,
            displayed_price=data.displayed_price,
            displayed_currency=data.displayed_currency.value,
            threshold=data.threshold,
            provider_observed_at=data.provider_observed_at,
            rate_observed_at=data.rate_observed_at,
        )
        self.session.add(round_)
        await self.session.flush()
        return round_

    async def get(self, round_id: str) -> Round | None:
        return await self.session.get(Round, round_id)

    async def latest_pending(self, session_id: str) -> Round | None:
        return await self.session.scalar(
            select(Round)
            .where(Round.session_id == session_id, Round.resolved_at.is_(None))
            .order_by(Round.created_at.desc())
            .limit(1)
        )

    async def latest(self, session_id: str) -> Round | None:
        return await self.session.scalar(
            select(Round)
            .where(Round.session_id == session_id)
            .order_by(Round.created_at.desc())
            .limit(1)
        )

    async def set_card_message_id(self, round_id: str, message_id: int) -> None:
        round_ = await self.get(round_id)
        if round_ is None:
            raise LookupError("round not found")
        round_.card_message_id = message_id
        await self.session.flush()

    async def resolve(
        self,
        round_id: str,
        *,
        correct: bool,
        answer: str,
        scorer_user_id: str | None = None,
    ) -> ResolveResult:
        round_ = await self.session.get(Round, round_id, with_for_update=True)
        if round_ is None:
            raise LookupError("round not found")
        if round_.resolved_at is not None:
            return ResolveResult(awarded_points=0, already_resolved=True)
        round_.answer = answer
        round_.correct = correct
        round_.resolved_at = datetime.now(UTC)
        awarded = 0
        if correct:
            game = await self.session.get(GameSession, round_.session_id)
            if game is None:
                raise LookupError("game session not found")
            user = await self.session.get(
                User, scorer_user_id or game.user_id, with_for_update=True
            )
            if user is None:
                raise LookupError("user not found")
            user.score += 1
            awarded = 1
        await self.session.flush()
        return ResolveResult(awarded_points=awarded, already_resolved=False)


class WhoCloserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def join(self, session_id: str, user_id: str) -> bool:
        existing = await self.session.scalar(
            select(WhoCloserParticipant).where(
                WhoCloserParticipant.session_id == session_id,
                WhoCloserParticipant.user_id == user_id,
            )
        )
        if existing is not None:
            return False
        self.session.add(WhoCloserParticipant(session_id=session_id, user_id=user_id))
        await self.session.flush()
        return True

    async def extend_once(self, session_id: str, user_id: str) -> bool:
        participant = await self.session.scalar(
            select(WhoCloserParticipant).where(
                WhoCloserParticipant.session_id == session_id,
                WhoCloserParticipant.user_id == user_id,
            )
        )
        if participant is None or participant.added_time:
            return False
        participant.added_time = True
        await self.session.flush()
        return True

    async def participants(self, session_id: str) -> list[WhoCloserParticipant]:
        rows = await self.session.scalars(
            select(WhoCloserParticipant).where(WhoCloserParticipant.session_id == session_id)
        )
        return list(rows)

    async def participant_users(self, session_id: str) -> list[tuple[int, str]]:
        rows = await self.session.execute(
            select(User.telegram_id, User.display_name)
            .join(WhoCloserParticipant, WhoCloserParticipant.user_id == User.id)
            .where(WhoCloserParticipant.session_id == session_id)
        )
        return list(rows.tuples())

    async def submit(self, round_id: str, user_id: str, price: Decimal) -> bool:
        exists = await self.session.scalar(
            select(WhoCloserAnswer).where(
                WhoCloserAnswer.round_id == round_id, WhoCloserAnswer.price == price
            )
        )
        if exists is not None:
            return False
        self.session.add(WhoCloserAnswer(round_id=round_id, user_id=user_id, price=price))
        await self.session.flush()
        return True

    async def answers(self, round_id: str) -> list[WhoCloserAnswer]:
        rows = await self.session.scalars(
            select(WhoCloserAnswer).where(WhoCloserAnswer.round_id == round_id)
        )
        return list(rows)
