from decimal import Decimal

import httpx
import pytest

pytestmark = pytest.mark.xfail(strict=True, reason="fixed vulnerability must not reproduce")
from aiogram.exceptions import TelegramBadRequest

from guess_price_bot.bot.routers.game import send_card
from guess_price_bot.domain.models import Currency, GameMode
from guess_price_bot.services.game import RoundView


class RejectingMessage:
    async def answer_photo(self, photo, **kwargs):
        if isinstance(photo, str):
            raise TelegramBadRequest(method=None, message="Telegram rejected image URL")

    async def answer(self, text, **kwargs):
        raise AssertionError(f"unexpected text fallback: {text}")


def untrusted_card(image_url: str) -> RoundView:
    return RoundView(
        id="round",
        mode=GameMode.GUESS,
        title="item",
        description="description",
        image_url=image_url,
        source_url="https://listing.example/item",
        displayed_price=Decimal("100"),
        currency=Currency.USD,
        threshold=None,
    )


async def test_rejected_untrusted_image_url_is_fetched_by_the_bot():
    fetched_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched_urls.append(str(request.url))
        return httpx.Response(200, content=b"image")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await send_card(
            RejectingMessage(),
            untrusted_card("http://169.254.169.254/latest/meta-data/"),
            client,
        )

    assert fetched_urls == ["http://169.254.169.254/latest/meta-data/"]
