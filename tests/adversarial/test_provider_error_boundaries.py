from datetime import UTC, datetime

import httpx
import pytest

from guess_price_bot.providers.cars import CarsProvider
from guess_price_bot.providers.contracts import ProviderUnavailable
from guess_price_bot.providers.food import FoodProvider
from guess_price_bot.providers.goods import GoodsProvider
from guess_price_bot.providers.realty import RealtyProvider


def client_for(payload: object) -> httpx.AsyncClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_goods_provider_contains_non_object_success_payload() -> None:
    async with client_for([]) as client:
        with pytest.raises(ProviderUnavailable):
            await GoodsProvider(client, "test-key").get_card()


async def test_food_provider_contains_item_without_id() -> None:
    payload = {
        "items": [
            {
                "product": {
                    "product_name": "Milk",
                    "image_url": "https://example.com/milk.jpg",
                },
                "date": "2026-08-30",
                "price": "1.25",
                "currency": "USD",
            }
        ]
    }
    async with client_for(payload) as client:
        provider = FoodProvider(client, now=lambda: datetime(2026, 8, 30, tzinfo=UTC))
        with pytest.raises(ProviderUnavailable):
            await provider.get_card()


async def test_cars_provider_contains_non_numeric_mileage() -> None:
    payload = {
        "data": [
            {
                "vin": "VIN-1",
                "vehicle": {"make": "Ford", "model": "Focus"},
                "retailListing": {
                    "price": "10000",
                    "vdp": "https://example.com/car",
                    "primaryImage": "https://example.com/car.jpg",
                    "miles": "unknown",
                },
            }
        ]
    }
    async with client_for(payload) as client:
        with pytest.raises(ProviderUnavailable):
            await CarsProvider(client, "test-key").get_card()


async def test_realty_provider_contains_non_numeric_area() -> None:
    payload = {
        "data": {
            "properties": [
                {
                    "externalID": "property-1",
                    "title": "Apartment",
                    "coverPhoto": {"url": "https://example.com/apartment.jpg"},
                    "price": "100000",
                    "area": "unknown",
                }
            ]
        }
    }
    async with client_for(payload) as client:
        with pytest.raises(ProviderUnavailable):
            await RealtyProvider(client, "test-key").get_card()
