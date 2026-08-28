from datetime import UTC, datetime
from decimal import Decimal

import pytest

pytestmark = pytest.mark.xfail(strict=True, reason="fixed vulnerability must not reproduce")
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from guess_price_bot.db.models import Base, GameSession, Round
from guess_price_bot.domain.models import Category, Currency, GameMode
from guess_price_bot.providers.contracts import ListingCard, RateSnapshot, TranslatedCard
from guess_price_bot.services.game import GameService, RateCache


class FakeProvider:
    async def get_card(self) -> ListingCard:
        return ListingCard(
            source="fake",
            source_id="item-1",
            title="Phone",
            description="Description",
            price=Decimal("100"),
            currency="USD",
            image_url="https://example.test/image.jpg",
            source_url="https://example.test/item",
            observed_at=datetime.now(UTC),
        )


class FakeTranslator:
    async def translate_card(self, title: str, description: str) -> TranslatedCard:
        return TranslatedCard(title=title, description=description)


class FakeRates:
    async def fetch(self) -> RateSnapshot:
        now = datetime.now(UTC)
        return RateSnapshot(rates={"USD": Decimal("1")}, provider_at=now, fetched_at=now)


def make_service(session) -> GameService:
    return GameService(
        session=session,
        providers={category: FakeProvider() for category in Category},
        translator=FakeTranslator(),
        rates=RateCache(FakeRates()),
    )


@pytest.mark.asyncio
async def test_any_group_member_can_stop_someone_elses_active_game():
    """PoC: an arbitrary group participant can terminate the owner's game."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = make_service(session)
        chat_id, owner_id, attacker_id = -100_123, 10, 20
        await service.start(owner_id, "owner", GameMode.GUESS, chat_id=chat_id)
        await service.select_category(owner_id, Category.GOODS, chat_id=chat_id)
        await service.select_currency(owner_id, Currency.USD, chat_id=chat_id)

        # The attacker is neither the creator nor an existing game member.
        await service.stop(attacker_id, chat_id=chat_id)

        game = await session.scalar(select(GameSession).where(GameSession.chat_id == chat_id))
        assert game is not None
        # `stop` never authenticates the caller in group-chat scope; it even
        # succeeds when the attacker has no user record at all.
        assert await service.users.by_telegram_id(attacker_id) is None
        assert game.status == "stopped"

    await engine.dispose()


@pytest.mark.asyncio
async def test_any_group_user_can_replace_the_owners_selected_category():
    """PoC: a non-owner can mutate an in-progress group game's configuration."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = make_service(session)
        chat_id, owner_id, attacker_id = -100_124, 10, 20
        await service.start(owner_id, "owner", GameMode.GUESS, chat_id=chat_id)
        await service.select_category(owner_id, Category.GOODS, chat_id=chat_id)

        await service.select_category(attacker_id, Category.CARS, chat_id=chat_id)

        game = await session.scalar(select(GameSession).where(GameSession.chat_id == chat_id))
        assert game is not None
        assert game.user_id == (await service.users.by_telegram_id(owner_id)).id
        assert game.category == Category.CARS.value
        assert await service.users.by_telegram_id(attacker_id) is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_any_group_user_can_replace_the_owners_active_game():
    """PoC: sending a new start request kills the current owner's group game."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = make_service(session)
        chat_id, owner_id, attacker_id = -100_125, 10, 20
        original_id = await service.start(owner_id, "owner", GameMode.GUESS, chat_id=chat_id)
        replacement_id = await service.start(
            attacker_id, "attacker", GameMode.MORE_LESS, chat_id=chat_id
        )

        games = list(
            (
                await session.scalars(
                    select(GameSession)
                    .where(GameSession.chat_id == chat_id)
                    .order_by(GameSession.created_at.asc())
                )
            ).all()
        )
        assert [game.id for game in games] == [original_id, replacement_id]
        assert [game.status for game in games] == ["stopped", "active"]
        assert games[0].user_id != games[1].user_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_replaying_currency_selection_creates_multiple_open_rounds():
    """PoC: a stale currency button creates extra unresolved rounds indefinitely."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = make_service(session)
        chat_id, owner_id = -100_126, 10
        await service.start(owner_id, "owner", GameMode.GUESS, chat_id=chat_id)
        await service.select_category(owner_id, Category.GOODS, chat_id=chat_id)

        await service.select_currency(owner_id, Currency.USD, chat_id=chat_id)
        await service.select_currency(owner_id, Currency.USD, chat_id=chat_id)

        open_rounds = await session.scalar(
            select(func.count())
            .select_from(Round)
            .join(GameSession)
            .where(GameSession.chat_id == chat_id, Round.resolved_at.is_(None))
        )
        assert open_rounds == 2

    await engine.dispose()


@pytest.mark.asyncio
async def test_non_owner_can_start_the_next_round_after_owner_finishes():
    """PoC: a participant can consume provider calls and control round progression."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = make_service(session)
        chat_id, owner_id, attacker_id = -100_127, 10, 20
        await service.start(owner_id, "owner", GameMode.GUESS, chat_id=chat_id)
        await service.select_category(owner_id, Category.GOODS, chat_id=chat_id)
        await service.select_currency(owner_id, Currency.USD, chat_id=chat_id)
        await service.answer_guess(attacker_id, "100", chat_id=chat_id, display_name="attacker")

        await service.next_round(attacker_id, chat_id=chat_id)

        game = await session.scalar(
            select(GameSession).where(
                GameSession.chat_id == chat_id, GameSession.status == "active"
            )
        )
        assert game is not None
        pending = await session.scalar(
            select(func.count()).select_from(Round).where(
                Round.session_id == game.id, Round.resolved_at.is_(None)
            )
        )
        assert pending == 1

    await engine.dispose()
