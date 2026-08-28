import asyncio
import random
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from guess_price_bot.db.models import Base
from guess_price_bot.domain.models import Category, Currency, GameMode
from guess_price_bot.providers.contracts import ListingCard, RateSnapshot, TranslatedCard
from guess_price_bot.services.game import GameService, RateCache


class FakeProvider:
    async def get_card(self) -> ListingCard:
        now = datetime.now(UTC)
        return ListingCard(
            source="fake",
            source_id="item-1",
            title="Phone",
            description="A new phone",
            price=Decimal("100"),
            currency="USD",
            image_url="https://example.com/image.jpg",
            source_url="https://example.com/item",
            observed_at=now,
        )


class FakeTranslator:
    async def translate_card(self, title: str, description: str) -> TranslatedCard:
        return TranslatedCard(title="Телефон", description="Новый телефон")


class FakeRates:
    calls = 0

    async def fetch(self) -> RateSnapshot:
        self.calls += 1
        now = datetime.now(UTC)
        return RateSnapshot(
            rates={"USD": Decimal("1"), "UAH": Decimal("40"), "RUB": Decimal("90")},
            provider_at=now,
            fetched_at=now,
        )


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def make_service(session, mode_provider=None):
    provider = mode_provider or FakeProvider()
    return GameService(
        session=session,
        providers={category: provider for category in Category},
        translator=FakeTranslator(),
        rates=RateCache(FakeRates()),
        rng=random.Random(3),
    )


async def test_guess_flow_translates_converts_and_awards_once(session):
    service = make_service(session)
    await service.start(10, "Анна", GameMode.GUESS)
    await service.select_category(10, Category.GOODS)
    card = await service.select_currency(10, Currency.UAH)

    assert card.title == "Телефон"
    assert card.displayed_price == Decimal("4000.00")
    result = await service.answer_guess(10, "4000")
    duplicate = await service.answer_guess(10, "4000")

    assert result.correct is True and result.awarded_points == 1
    assert duplicate.already_resolved is True and duplicate.awarded_points == 0
    assert await service.score(10) == 1


async def test_more_less_uses_hidden_real_price_and_generated_threshold(session):
    service = make_service(session)
    await service.start(20, "Богдан", GameMode.MORE_LESS)
    await service.select_category(20, Category.CARS)
    card = await service.select_currency(20, Currency.USD)

    assert Decimal("50") <= card.threshold <= Decimal("150")
    assert card.threshold != Decimal("100")
    expected = "more" if Decimal("100") > card.threshold else "less"
    result = await service.answer_comparison(20, expected)

    assert result.correct is True and result.awarded_points == 1


async def test_rate_cache_reuses_snapshot():
    provider = FakeRates()
    cache = RateCache(provider)
    first = await cache.get()
    second = await cache.get()
    assert first is second
    assert provider.calls == 1


async def test_rate_cache_returns_fresh_snapshot_while_forced_refresh_is_running():
    refresh_started = asyncio.Event()
    release_refresh = asyncio.Event()

    class BlockingRates(FakeRates):
        async def fetch(self) -> RateSnapshot:
            if self.calls:
                refresh_started.set()
                await release_refresh.wait()
            return await super().fetch()

    cache = RateCache(BlockingRates())
    original = await cache.get()
    refresh = asyncio.create_task(cache.get(force=True))
    await refresh_started.wait()

    cached = await asyncio.wait_for(cache.get(), timeout=0.05)
    assert cached is original

    release_refresh.set()
    await refresh


async def test_card_and_exchange_rates_are_loaded_concurrently(session):
    card_started = asyncio.Event()
    rates_started = asyncio.Event()

    class CoordinatedProvider(FakeProvider):
        async def get_card(self) -> ListingCard:
            card_started.set()
            await asyncio.wait_for(rates_started.wait(), timeout=0.1)
            return await super().get_card()

    class CoordinatedRates(FakeRates):
        async def fetch(self) -> RateSnapshot:
            rates_started.set()
            await asyncio.wait_for(card_started.wait(), timeout=0.1)
            return await super().fetch()

    service = GameService(
        session=session,
        providers={category: CoordinatedProvider() for category in Category},
        translator=FakeTranslator(),
        rates=RateCache(CoordinatedRates()),
        rng=random.Random(3),
    )
    await service.start(30, "Олег", GameMode.GUESS)
    await service.select_category(30, Category.GOODS)

    card = await service.select_currency(30, Currency.UAH)

    assert card.displayed_price == Decimal("4000.00")


async def test_group_guess_awards_global_point_to_correct_participant(session):
    service = make_service(session)
    await service.start(10, "Автор", GameMode.GUESS, chat_id=-1001)
    await service.select_category(10, Category.GOODS, chat_id=-1001)
    await service.select_currency(10, Currency.UAH, chat_id=-1001)

    result = await service.answer_guess(
        20, "4000", chat_id=-1001, display_name="Победитель"
    )

    assert result.correct is True and result.awarded_points == 1
    assert await service.score(10) == 0
    assert await service.score(20) == 1


async def test_wrong_group_guess_keeps_round_open(session):
    service = make_service(session)
    await service.start(10, "Автор", GameMode.GUESS, chat_id=-1001)
    await service.select_category(10, Category.GOODS, chat_id=-1001)
    await service.select_currency(10, Currency.UAH, chat_id=-1001)

    wrong = await service.answer_guess(20, "1", chat_id=-1001, display_name="Игрок")
    winner = await service.answer_guess(21, "4000", chat_id=-1001, display_name="Другой")

    assert wrong.correct is False and wrong.round_continues is True
    assert winner.correct is True and winner.awarded_points == 1


async def test_group_comparison_rejects_non_owner(session):
    service = make_service(session)
    await service.start(10, "Автор", GameMode.MORE_LESS, chat_id=-1001)
    await service.select_category(10, Category.CARS, chat_id=-1001)
    await service.select_currency(10, Currency.USD, chat_id=-1001)

    with pytest.raises(PermissionError):
        await service.answer_comparison(20, "more", chat_id=-1001)


async def test_score_in_chat_registers_member_and_returns_global_score(session):
    service = make_service(session)
    user = await service.users.get_or_create(40, "Мария")
    user.score = 7
    await session.commit()

    score = await service.score_in_chat(-1001, 40, "Мария")

    assert score == 7
    assert await service.rating(-1001) == [("Мария", 7)]
