from decimal import Decimal, InvalidOperation

import httpx
import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.token import TokenValidationError

from guess_price_bot.bot.routers.game import send_card
from guess_price_bot.config import Settings
from guess_price_bot.domain.models import Category, Currency, GameMode
from guess_price_bot.domain.scoring import evaluate_guess
from guess_price_bot.providers.exchange_rates import ExchangeRateProvider
from guess_price_bot.services.game import RoundView


class RejectingImageMessage:
    def __init__(self) -> None:
        self.fallbacks: list[str] = []

    async def answer_photo(self, photo, **kwargs):
        if isinstance(photo, str):
            raise TelegramBadRequest(method=None, message="URL rejected")

    async def answer(self, text, **kwargs):
        self.fallbacks.append(text)


class OversizedImageStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.chunks_sent = 0

    async def __aiter__(self):
        for _ in range(11):
            self.chunks_sent += 1
            yield b"x" * 1024 * 1024

    async def aclose(self) -> None:
        pass


def card() -> RoundView:
    return RoundView(
        id="round",
        mode=GameMode.GUESS,
        title="item",
        description="description",
        image_url="https://upstream.example/huge-image",
        source_url="https://listing.example/item",
        displayed_price=Decimal("100"),
        currency=Currency.USD,
        threshold=None,
    )


@pytest.mark.xfail(strict=True, reason="fixed vulnerability must not reproduce")
async def test_oversized_image_is_fully_downloaded_before_size_limit_is_checked():
    stream = OversizedImageStream()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        message = RejectingImageMessage()
        await send_card(message, card(), client)

    assert stream.chunks_sent == 11
    assert message.fallbacks


@pytest.mark.parametrize(
"payload",
[
    {"timestamp": 1, "rates": []},
    {"timestamp": None, "rates": {"UAH": 40}},
],
)
@pytest.mark.xfail(strict=True, reason="fixed vulnerability must not reproduce")
async def test_corrupted_exchange_rate_payload_escapes_provider_error_boundary(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ExchangeRateProvider(client, "test-app-id")
        with pytest.raises((AttributeError, TypeError)):
            await provider.fetch()


@pytest.mark.xfail(strict=True, reason="fixed vulnerability must not reproduce")
async def test_non_finite_upstream_rate_poisoning_breaks_guess_evaluation():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"timestamp": 1, "rates": {"UAH": "NaN"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        snapshot = await ExchangeRateProvider(client, "test-app-id").fetch()

    poisoned_price = snapshot.convert(Decimal("1"), "USD", "UAH")

    assert poisoned_price.is_nan()
    with pytest.raises(InvalidOperation):
        evaluate_guess(poisoned_price, Decimal("1"), Category.GOODS)


@pytest.mark.xfail(strict=True, reason="fixed vulnerability must not reproduce")
def test_empty_required_settings_are_accepted_then_bot_initialization_crashes(monkeypatch):
    for name in (
        "BOT_TOKEN",
        "DATABASE_URL",
        "SERPAPI_API_KEY",
        "AUTO_DEV_API_KEY",
        "RAPIDAPI_KEY",
        "OPEN_EXCHANGE_RATES_APP_ID",
    ):
        monkeypatch.setenv(name, "")

    settings = Settings()

    assert settings.bot_token.get_secret_value() == ""
    with pytest.raises(TokenValidationError):
        Bot(token=settings.bot_token.get_secret_value())
