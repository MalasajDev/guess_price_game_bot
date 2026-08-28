import pytest

pytestmark = pytest.mark.xfail(strict=True, reason="fixed vulnerability must not reproduce")
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from guess_price_bot.db.models import Base, GameSession, User
from guess_price_bot.domain.models import GameMode


@pytest.mark.asyncio
async def test_database_permits_multiple_active_games_in_one_group():
    """PoC: the persisted outcome of two raced starts breaks group-game lookup."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        first = User(telegram_id=1, display_name="user-1")
        second = User(telegram_id=2, display_name="user-2")
        session.add_all([first, second])
        await session.flush()
        session.add_all(
            [
                GameSession(
                    user_id=first.id, chat_id=-100, mode=GameMode.GUESS.value, status="active"
                ),
                GameSession(
                    user_id=second.id, chat_id=-100, mode=GameMode.GUESS.value, status="active"
                ),
            ]
        )
        await session.commit()
        active_count = await session.scalar(
            select(func.count()).select_from(GameSession).where(
                GameSession.chat_id == -100, GameSession.status == "active"
            )
        )
        assert active_count == 2

    await engine.dispose()
