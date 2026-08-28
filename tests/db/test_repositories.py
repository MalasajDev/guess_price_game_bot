from datetime import UTC, datetime
from decimal import Decimal

from guess_price_bot.db.models import GameSession, Round
from guess_price_bot.db.repositories import (
    GameSessionRepository,
    NewRound,
    RoundRepository,
    UserRepository,
)
from guess_price_bot.domain.models import Category, Currency, GameMode


def frozen_round() -> NewRound:
    now = datetime.now(UTC)
    return NewRound(
        provider="serpapi_google_shopping",
        source_listing_id="item-1",
        source_url="https://example/item-1",
        image_url="https://example/item-1.jpg",
        source_title="Camera",
        source_description="A camera",
        translated_title="Камера",
        translated_description="Фотоаппарат",
        source_price=Decimal("10"),
        source_currency="EUR",
        conversion_rate=Decimal("40"),
        displayed_price=Decimal("400"),
        displayed_currency=Currency.UAH,
        provider_observed_at=now,
        rate_observed_at=now,
        threshold=None,
    )


async def test_correct_round_increments_score_once(db_session):
    users = UserRepository(db_session)
    sessions = GameSessionRepository(db_session)
    rounds = RoundRepository(db_session)
    user = await users.get_or_create(telegram_id=1, display_name="Ada")
    game = await sessions.start(user.id, GameMode.GUESS)
    await sessions.configure(game.id, Category.GOODS, Currency.UAH)
    round_ = await rounds.create_pending(game.id, frozen_round())

    first = await rounds.resolve(round_.id, correct=True, answer="400")
    second = await rounds.resolve(round_.id, correct=True, answer="400")

    assert first.awarded_points == 1
    assert second.already_resolved is True
    assert await users.score_for(user.id) == 1


async def test_start_closes_previous_active_session(db_session):
    users = UserRepository(db_session)
    sessions = GameSessionRepository(db_session)
    user = await users.get_or_create(telegram_id=2, display_name="Lin")
    first = await sessions.start(user.id, GameMode.GUESS)

    second = await sessions.start(user.id, GameMode.MORE_LESS)

    assert first.id != second.id
    assert (await sessions.get(first.id)).status == "stopped"
    assert (await sessions.get_active_for_user(user.id)).id == second.id


async def test_chat_has_one_active_game(db_session):
    users = UserRepository(db_session)
    sessions = GameSessionRepository(db_session)
    owner = await users.get_or_create(telegram_id=10, display_name="Анна")

    first = await sessions.start(owner.id, GameMode.GUESS, chat_id=-1001)
    second = await sessions.start(owner.id, GameMode.MORE_LESS, chat_id=-1001)

    assert first.status == "stopped"
    assert (await sessions.get_active_for_chat(-1001)).id == second.id


async def test_rating_uses_global_scores_of_group_participants(db_session):
    users = UserRepository(db_session)
    anna = await users.get_or_create(telegram_id=11, display_name="Анна")
    bogdan = await users.get_or_create(telegram_id=12, display_name="Богдан")
    outsider = await users.get_or_create(telegram_id=13, display_name="Вне группы")
    anna.score, bogdan.score, outsider.score = 2, 1, 100
    await users.register_in_chat(-1001, anna.id)
    await users.register_in_chat(-1001, bogdan.id)

    assert await users.rating_for_chat(-1001) == [("Анна", 2), ("Богдан", 1)]


async def test_round_awards_answering_user_not_game_owner(db_session):
    users = UserRepository(db_session)
    sessions = GameSessionRepository(db_session)
    rounds = RoundRepository(db_session)
    owner = await users.get_or_create(telegram_id=20, display_name="Автор")
    winner = await users.get_or_create(telegram_id=21, display_name="Победитель")
    game = await sessions.start(owner.id, GameMode.GUESS, chat_id=-1001)
    round_ = await rounds.create_pending(game.id, frozen_round())

    await rounds.resolve(round_.id, correct=True, answer="400", scorer_user_id=winner.id)

    assert await users.score_for(owner.id) == 0
    assert await users.score_for(winner.id) == 1


def test_hot_game_queries_have_composite_indexes():
    game_indexes = {index.name for index in GameSession.__table__.indexes}
    round_indexes = {index.name for index in Round.__table__.indexes}

    assert "ix_game_sessions_chat_status" in game_indexes
    assert "ix_game_sessions_user_status" in game_indexes
    assert "ix_rounds_session_resolved_created" in round_indexes
