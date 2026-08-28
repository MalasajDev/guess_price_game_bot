from decimal import Decimal

import httpx
from aiogram.exceptions import TelegramBadRequest

from guess_price_bot.bot.routers.game import send_card
from guess_price_bot.domain.models import Currency, GameMode
from guess_price_bot.services.game import RoundView


class FakeMessage:
    def __init__(self, *, reject_url: bool = False) -> None:
        self.photo = None
        self.text = None
        self.reject_url = reject_url

    async def answer_photo(self, photo, **kwargs):
        if self.reject_url and isinstance(photo, str):
            raise TelegramBadRequest(method=None, message="Telegram cannot fetch image")
        self.photo = photo

    async def answer(self, text, **kwargs):
        self.text = text


def card() -> RoundView:
    return RoundView(
        id="1",
        mode=GameMode.GUESS,
        title="Автомобиль",
        description="Описание",
        image_url="https://cdn.example/image.jpg",
        source_url="https://source.example/item",
        displayed_price=Decimal("100"),
        currency=Currency.USD,
        threshold=None,
    )


async def test_send_card_lets_telegram_fetch_image_directly():
    message = FakeMessage()

    def handler(request):
        raise AssertionError("bot must not download an image accepted by Telegram")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await send_card(message, card(), client)

    assert message.photo == card().image_url


async def test_send_card_falls_back_to_text_when_telegram_rejects_url():
    message = FakeMessage(reject_url=True)

    def handler(request):
        return httpx.Response(200, content=b"jpeg-data")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await send_card(message, card(), client)

    assert message.photo is None
    assert message.text is not None


async def test_send_card_falls_back_to_text_when_image_download_fails():
    message = FakeMessage(reject_url=True)

    def handler(request):
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await send_card(message, card(), client)

    assert message.photo is None
    assert "Автомобиль" in message.text
