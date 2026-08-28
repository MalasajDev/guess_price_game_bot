from datetime import UTC, datetime
from decimal import Decimal

import httpx

from guess_price_bot.providers.exchange_rates import ExchangeRateProvider


async def test_rate_provider_converts_between_non_usd_currencies(client_factory):
    def handler(request):
        return httpx.Response(
            200,
            json={"timestamp": 1787702400, "base": "USD", "rates": {"EUR": 0.8, "UAH": 40}},
        )

    async with client_factory(handler) as client:
        provider = ExchangeRateProvider(client, "app-id")
        snapshot = await provider.fetch()

    assert snapshot.convert(Decimal("10"), "EUR", "UAH") == Decimal("500.00")
    assert snapshot.provider_at == datetime.fromtimestamp(1787702400, tz=UTC)
