from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx

from guess_price_bot.providers.contracts import ProviderUnavailable, RateSnapshot, utc_now


class ExchangeRateProvider:
    endpoint = "https://openexchangerates.org/api/latest.json"

    def __init__(self, client: httpx.AsyncClient, app_id: str) -> None:
        self.client = client
        self.app_id = app_id

    async def fetch(self) -> RateSnapshot:
        try:
            response = await self.client.get(self.endpoint, params={"app_id": self.app_id})
            response.raise_for_status()
            payload = response.json()
            rates = {key.upper(): Decimal(str(value)) for key, value in payload["rates"].items()}
            if not rates or any(not rate.is_finite() or rate <= 0 for rate in rates.values()):
                raise ValueError("exchange rates must be finite positive numbers")
            rates["USD"] = Decimal("1")
            provider_at = datetime.fromtimestamp(payload["timestamp"], tz=UTC)
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            InvalidOperation,
        ) as error:
            raise ProviderUnavailable("exchange-rate provider unavailable") from error
        return RateSnapshot(rates=rates, provider_at=provider_at, fetched_at=utc_now())
