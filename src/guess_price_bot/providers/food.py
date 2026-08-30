from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx

from guess_price_bot.providers.contracts import (
    ListingCard,
    ProviderUnavailable,
    decimal_price,
    utc_now,
)


class FoodProvider:
    endpoint = "https://prices.openfoodfacts.org/api/v1/prices"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        now: Callable[[], datetime] = utc_now,
        max_age: timedelta = timedelta(days=90),
    ) -> None:
        self.client = client
        self.now = now
        self.max_age = max_age

    async def get_card(self) -> ListingCard:
        try:
            response = await self.client.get(
                self.endpoint,
                params={
                    "order_by": "-date",
                    "size": 100,
                    "date__gte": (self.now() - self.max_age).date().isoformat(),
                },
                headers={"User-Agent": "GuessPriceBot/0.1 (Telegram bot)"},
            )
            response.raise_for_status()
            payload = response.json()
            item = next(
                value
                for value in payload.get("items", payload.get("results", []))
                if self._usable(value)
            )
        except (httpx.HTTPError, ValueError, StopIteration) as error:
            raise ProviderUnavailable("food provider returned no recent usable price") from error
        product = item["product"]
        observed_at = _parse_date(item["date"])
        details = " · ".join(
            part
            for part in (str(product.get("brands") or ""), str(product.get("quantity") or ""))
            if part
        )
        return ListingCard(
            source="open_prices",
            source_id=str(item["id"]),
            title=str(product["product_name"]),
            description=details or "Food product",
            price=decimal_price(item["price"]),
            currency=str(item["currency"]).upper(),
            image_url=str(product["image_url"]),
            source_url=f"https://prices.openfoodfacts.org/prices/{item['id']}",
            observed_at=observed_at,
        )

    def _usable(self, item: dict) -> bool:
        if not isinstance(item, dict):
            return False
        product = item.get("product") or {}
        if not isinstance(product, dict):
            return False
        try:
            observed = _parse_date(item["date"])
            decimal_price(item.get("price"))
        except (KeyError, TypeError, ValueError, ProviderUnavailable):
            return False
        return bool(
            item.get("id")
            and product.get("product_name")
            and product.get("image_url")
            and item.get("currency")
            and self.now() - observed <= self.max_age
        )


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)
