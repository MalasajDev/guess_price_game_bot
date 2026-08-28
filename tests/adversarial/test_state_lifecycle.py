import asyncio
import random
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
            description="A new phone",
            price=Decimal("100"),
            currency="USD",
            image_url="https://example.com/image.jpg",
            source_url="https://example.com/item",
            observed_at=datetime.now(UTC),
        )


class FakeTranslator:
    async def translate_card(self, title: str, description: str) -> TranslatedCard:
        return TranslatedCard(title=title, description=description)


class FakeRates:
    async def fetch(self) -> RateSnapshot:
        now = datetime.now(UTC)
        return RateSnapshot(
            rates={"USD": Decimal("1"), "UAH": Decimal("40"), "RUB": Decimal("90")},
            provider_at=now,
            fetched_at=now,
        )


def make_service(session) -> GameService:
    provider = FakeProvider()
    return GameService(
        session=session,
        providers={category: provider for category in Category},
        translator=FakeTranslator(),
        rates=RateCache(FakeRates()),
        rng=random.Random(3),
    )


@pytest.mark.asyncio
async def test_replaying_currency_callback_creates_multiple_open_rounds():
    """PoC: a stale currency button can create unlimited simultaneous rounds."""
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

        await service.answer_guess(owner_id, "100", chat_id=chat_id)
        with pytest.raises(ValueError, match="finish the current round first"):
            await service.next_round(owner_id, chat_id=chat_id)

    await engine.dispose()


@pytest.mark.asyncio
async def test_stale_category_callback_mutates_config_while_a_round_is_open():
    """PoC: an old category button changes the next game's category mid-round."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = make_service(session)
        chat_id, owner_id = -100_127, 11
        await service.start(owner_id, "owner", GameMode.GUESS, chat_id=chat_id)
        await service.select_category(owner_id, Category.GOODS, chat_id=chat_id)
        await service.select_currency(owner_id, Currency.USD, chat_id=chat_id)

        await service.select_category(owner_id, Category.CARS, chat_id=chat_id)

        game = await session.scalar(
            select(GameSession).where(GameSession.chat_id == chat_id, GameSession.status == "active")
        )
        open_rounds = await session.scalar(
            select(func.count()).select_from(Round).where(Round.session_id == game.id, Round.resolved_at.is_(None))
        )
        assert game.category == Category.CARS.value
        assert open_rounds == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_simultaneous_next_round_callbacks_create_two_open_rounds(tmp_path, monkeypatch):
    """PoC: concurrent replayed next-round callbacks bypass the pending-round check."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'next-round-race.db'}", connect_args={"timeout": 10}
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    chat_id, owner_id = -100_128, 12

    async with factory() as session:
        service = make_service(session)
        await service.start(owner_id, "owner", GameMode.GUESS, chat_id=chat_id)
        await service.select_category(owner_id, Category.GOODS, chat_id=chat_id)
        await service.select_currency(owner_id, Currency.USD, chat_id=chat_id)
        await service.answer_guess(owner_id, "100", chat_id=chat_id)

    original_create_round = GameService._create_round
    both_checked = asyncio.Event()
    entered = 0

    async def wait_until_both_checked(service, game):
        nonlocal entered
        entered += 1
        if entered == 2:
            both_checked.set()
        await asyncio.wait_for(both_checked.wait(), timeout=1)
        return await original_create_round(service, game)

    monkeypatch.setattr(GameService, "_create_round", wait_until_both_checked)

    async def click_next_round():
        async with factory() as session:
            return await make_service(session).next_round(owner_id, chat_id=chat_id)

    await asyncio.gather(click_next_round(), click_next_round())

    async with factory() as session:
        open_rounds = await session.scalar(
            select(func.count())
            .select_from(Round)
            .join(GameSession)
            .where(GameSession.chat_id == chat_id, Round.resolved_at.is_(None))
        )
        assert open_rounds == 2

    await engine.dispose()
