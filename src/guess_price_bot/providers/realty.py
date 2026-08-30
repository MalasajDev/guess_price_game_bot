import random

import httpx

from guess_price_bot.providers.contracts import (
    ListingCard,
    ProviderUnavailable,
    decimal_price,
    utc_now,
)


class RealtyProvider:
    endpoint = "https://uae-real-estate3.p.rapidapi.com/search-property"
    host = "uae-real-estate3.p.rapidapi.com"

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
        self._properties: list[dict] = []

    async def get_card(self) -> ListingCard:
        if not self._properties:
            await self._refresh()
        return _card(self._properties.pop())

    async def _refresh(self) -> None:
        try:
            response = await self.client.get(
                self.endpoint,
                params={
                    "purpose": "for-sale",
                    "page": self.rng.randint(1, 20),
                    "langs": "en",
                    "property_type": "residential",
                    "sort_order": "latest",
                },
                headers={
                    "x-rapidapi-key": self.api_key,
                    "x-rapidapi-host": self.host,
                },
            )
            response.raise_for_status()
            self._properties = [
                item for item in response.json()["data"]["properties"] if _usable(item)
            ]
            self.rng.shuffle(self._properties)
            if not self._properties:
                raise ValueError("empty property result")
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderUnavailable("property listings unavailable") from error


def _usable(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    try:
        usable = bool(
            item.get("externalID")
            and _title(item)
            and item.get("coverPhoto", {}).get("url")
            and decimal_price(item.get("price"))
        )
        if item.get("area"):
            _format_area(item["area"])
        return usable
    except (AttributeError, ProviderUnavailable, TypeError, ValueError):
        return False


def _card(item: dict) -> ListingCard:
    location = ", ".join(_location_name(value) for value in item.get("location", []))
    description = " · ".join(
        value
        for value in (
            location,
            _format_area(item["area"]) if item.get("area") else "",
            f"{item['rooms']} bedrooms" if item.get("rooms") is not None else "",
            f"{item['baths']} bathrooms" if item.get("baths") is not None else "",
        )
        if value
    )
    listing_id = str(item["externalID"])
    return ListingCard(
        source="bayut_api",
        source_id=listing_id,
        title=_title(item),
        description=description,
        price=decimal_price(item["price"]),
        currency=str(item.get("currency") or "AED").upper(),
        image_url=str(item["coverPhoto"]["url"]),
        source_url=f"https://www.bayut.com/property/details-{listing_id}.html",
        observed_at=utc_now(),
    )


def _title(item: dict) -> str:
    title = item.get("title") or ""
    if isinstance(title, dict):
        return str(title.get("en") or next(iter(title.values()), ""))
    return str(title)


def _location_name(item: object) -> str:
    if isinstance(item, dict):
        name = item.get("name") or ""
        if isinstance(name, dict):
            return str(name.get("en") or next(iter(name.values()), ""))
        return str(name)
    return str(item)


def _format_area(value: object) -> str:
    return f"{float(value):g} ft²"
