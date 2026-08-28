from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.xfail(strict=True, reason="fixed vulnerability must not reproduce")

from guess_price_bot.bot.routers.game import price_guess, select_category, select_currency
from guess_price_bot.bot.routers.score import rating_command, score_command
from guess_price_bot.bot.routers.start import select_mode, start_mode
from guess_price_bot.domain.models import GameMode


class _UnusedGameService:
    async def start(self, *args, **kwargs):
        raise AssertionError("the handler must reject the update before calling the service")

    async def select_category(self, *args, **kwargs):
        raise AssertionError("the handler must reject the update before calling the service")

    async def answer_guess(self, *args, **kwargs):
        raise AssertionError("the handler must reject the update before calling the service")

    async def score_in_chat(self, *args, **kwargs):
        raise AssertionError("the handler must reject the update before calling the service")

    async def register_member(self, *args, **kwargs):
        raise AssertionError("the handler must reject the update before calling the service")


class _App:
    @asynccontextmanager
    async def session_factory(self):
        yield object()

    def game(self, session):
        return _UnusedGameService()


@pytest.mark.parametrize(
    ("handler", "data", "needs_message"),
    [
        (select_mode, "mode:retired_mode", True),
        (select_category, "category:retired_category", False),
        (select_currency, "currency:retired_currency", False),
    ],
)
async def test_removed_callback_option_crashes_its_handler(handler, data, needs_message):
    """PoC: an old inline button with a removed enum member raises ValueError."""
    callback = SimpleNamespace(data=data, message=object() if needs_message else None)

    with pytest.raises(ValueError):
        await handler(callback, None)


async def test_category_callback_without_message_crashes_before_a_response():
    """PoC: an inline callback has no Message, but category selection dereferences it."""
    callback = SimpleNamespace(
        data="category:goods",
        from_user=SimpleNamespace(id=1),
        message=None,
    )

    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'chat'"):
        await select_category(callback, _App())


@pytest.mark.parametrize(
    ("handler", "extra_args"),
    [
        (start_mode, (GameMode.GUESS,)),
        (price_guess, ()),
        (score_command, ()),
        (rating_command, ()),
    ],
)
async def test_sender_chat_message_crashes_user_dependent_handlers(handler, extra_args):
    """PoC: Telegram messages sent as a chat omit from_user and crash these handlers."""
    message = SimpleNamespace(
        chat=SimpleNamespace(id=-100_123),
        from_user=None,
        text="100",
    )

    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'id'"):
        await handler(message, _App(), *extra_args)
