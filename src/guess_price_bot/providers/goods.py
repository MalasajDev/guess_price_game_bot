import random

import httpx

from guess_price_bot.providers.contracts import (
    ListingCard,
    ProviderQuotaExceeded,
    ProviderUnavailable,
    decimal_price,
    utc_now,
)


class GoodsProvider:
    endpoint = "https://serpapi.com/search.json"

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        *,
        queries: tuple[str, ...] = (
            "headphones", "smartphone", "laptop", "tablet", "smartwatch",
            "camera", "gaming console", "television", "wireless speaker", "monitor",
            "robot vacuum", "air fryer", "coffee machine", "electric scooter", "drone",
        ),
        rng: random.Random | None = None,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.queries = queries
        self.rng = rng or random.Random()

    async def get_card(self) -> ListingCard:
        try:
            for attempt in range(2):
                try:
                    response = await self.client.get(
                        self.endpoint,
                        params={
                            "api_key": self.api_key,
                            "engine": "google_shopping",
                            "q": self.rng.choice(self.queries),
                            "gl": "us",
                            "hl": "en",
                        },
                    )
                    if response.status_code < 500 or attempt == 1:
                        break
                except httpx.TimeoutException:
                    if attempt == 1:
                        raise
            if response.status_code in (402, 403, 429):
                raise ProviderQuotaExceeded("SerpApi quota exhausted")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("unexpected response payload")
            products = payload.get("shopping_results", [])
            usable = [item for item in products if _usable(item)]
            item = self.rng.choice(usable)
            return ListingCard(
                source="serpapi_google_shopping",
                source_id=str(item["product_id"]),
                title=str(item["title"]),
                description=str(
                    item.get("snippet") or item.get("source") or "Google Shopping offer"
                ),
                price=decimal_price(item["extracted_price"]),
                currency="USD",
                image_url=str(item["thumbnail"]),
                source_url=str(item["product_link"]),
                observed_at=utc_now(),
            )
        except ProviderQuotaExceeded:
            raise
        except (httpx.HTTPError, IndexError, KeyError, TypeError, ValueError):
            raise ProviderUnavailable("SerpApi returned no usable product") from None


def _usable(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    try:
        decimal_price(item.get("extracted_price"))
    except ProviderUnavailable:
        return False
    return bool(
        item.get("product_id")
        and item.get("title")
        and item.get("thumbnail")
        and item.get("product_link")
    )
