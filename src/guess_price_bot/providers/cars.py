import random
from datetime import datetime

import httpx

from guess_price_bot.providers.contracts import (
    ListingCard,
    ProviderUnavailable,
    decimal_price,
    utc_now,
)


class CarsProvider:
    endpoint = "https://api.auto.dev/listings"
    makes = (
        "Toyota", "Honda", "Ford", "Chevrolet", "Volkswagen", "BMW", "Mercedes-Benz",
        "Audi", "Nissan", "Mazda", "Hyundai", "Kia", "Volvo", "Subaru", "Tesla",
    )

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        *,
        rng: random.Random | None = None,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.rng = rng or random.Random()
        self._listings: list[dict] = []

    async def get_card(self) -> ListingCard:
        if not self._listings:
            await self._refresh_listings()
        return _card(self._listings.pop())

    async def _refresh_listings(self) -> None:
        try:
            for attempt in range(2):
                try:
                    response = await self.client.get(
                        self.endpoint,
                        params={
                            "limit": 20,
                            "sort": "updatedAt.desc",
                            "vehicle.make": ",".join(self.makes),
                        },
                        headers=self._headers,
                    )
                    if response.status_code < 500 or attempt == 1:
                        break
                except httpx.TimeoutException:
                    if attempt == 1:
                        raise
            response.raise_for_status()
            self._listings = [item for item in response.json()["data"] if _usable(item)]
            self.rng.shuffle(self._listings)
            if not self._listings:
                raise ValueError("empty listing result")
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise ProviderUnavailable("Auto.dev listings unavailable") from None

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}


def _usable(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    vehicle = item.get("vehicle") or {}
    listing = item.get("retailListing") or {}
    if not isinstance(vehicle, dict) or not isinstance(listing, dict):
        return False
    try:
        decimal_price(listing.get("price"))
        if listing.get("miles") is not None:
            int(listing["miles"])
    except (ProviderUnavailable, TypeError, ValueError):
        return False
    return bool(
        item.get("vin")
        and vehicle.get("make")
        and vehicle.get("model")
        and listing.get("vdp")
        and listing.get("primaryImage")
    )


def _card(item: dict) -> ListingCard:
    vehicle = item["vehicle"]
    listing = item["retailListing"]
    title = " ".join(
        str(value)
        for value in (vehicle.get("year"), vehicle["make"], vehicle["model"], vehicle.get("trim"))
        if value
    )
    description = " · ".join(
        value
        for value in (
            f"{int(listing['miles']):,} miles" if listing.get("miles") is not None else "",
            str(listing.get("dealer") or ""),
            " ".join(str(listing.get(key) or "") for key in ("city", "state")).strip(),
        )
        if value
    )
    return ListingCard(
        source="auto_dev",
        source_id=str(item["vin"]),
        title=title,
        description=description,
        price=decimal_price(listing["price"]),
        currency="USD",
        image_url=str(listing["primaryImage"]),
        source_url=str(listing["vdp"]),
        observed_at=_parse_datetime(item.get("updatedAt")),
    )


def _parse_datetime(value: object) -> datetime:
    if not value:
        return utc_now()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return utc_now()
