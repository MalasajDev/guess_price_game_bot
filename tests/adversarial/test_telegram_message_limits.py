from decimal import Decimal
from types import SimpleNamespace

import httpx
from aiogram.exceptions import TelegramBadRequest

from guess_price_bot.bot.routers.game import send_card
from guess_price_bot.bot.routers.score import rating_command
from guess_price_bot.domain.models import Currency, GameMode
from guess_price_bot.services.game import RoundView


class LimitCheckingMessage:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(type="private")
        self.texts: list[str] = []

    async def answer_photo(self, photo: str, *, caption: str, **_kwargs):
        if len(caption) > 1024:
            raise TelegramBadRequest(method=None, message="caption is too long")
        return SimpleNamespace(message_id=1)

    async def answer(self, text: str, **_kwargs):
        if len(text) > 4096:
            raise TelegramBadRequest(method=None, message="message is too long")
        self.texts.append(text)
        return SimpleNamespace(message_id=2)


class FakeSessionFactory:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args) -> None:
        return None


class LargeRatingService:
    async def register_member(self, *_args) -> None:
        return None

    async def rating(self, _chat_id: int) -> list[tuple[str, int]]:
        return [(f"Participant {index:04d} with long name", index) for index in range(300)]


class LargeRatingApp:
    def session_factory(self) -> FakeSessionFactory:
        return FakeSessionFactory()

    def game(self, _session) -> LargeRatingService:
        return LargeRatingService()


async def test_oversized_provider_text_does_not_escape_telegram_fallback() -> None:
    card = RoundView(
        id="round-1",
        mode=GameMode.GUESS,
        title="A" * 5000,
        description="description",
        image_url="https://example.com/image.jpg",
        source_url="https://example.com/item",
        displayed_price=Decimal("100"),
        currency=Currency.USD,
        threshold=None,
    )

    async with httpx.AsyncClient() as client:
        sent = await send_card(LimitCheckingMessage(), card, client)

    assert sent.message_id == 2


async def test_large_group_rating_is_split_into_telegram_sized_messages() -> None:
    message = LimitCheckingMessage()
    message.chat.id = -1001
    message.from_user = SimpleNamespace(id=1, full_name="Requester")

    await rating_command(message, LargeRatingApp())

    assert len(message.texts) > 1
