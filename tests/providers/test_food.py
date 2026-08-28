from datetime import UTC, datetime
from decimal import Decimal

import httpx

from guess_price_bot.providers.food import FoodProvider


async def test_food_provider_uses_recent_price_with_product_image(client_factory):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 42,
                        "price": "2.79",
                        "currency": "EUR",
                        "date": "2026-08-20",
                        "product": {
                            "product_name": "Italian Pasta",
                            "brands": "Example",
                            "quantity": "500 g",
                            "image_url": "https://images.example/pasta.jpg",
                        },
                    }
                ]
            },
        )

    async with client_factory(handler) as client:
        card = await FoodProvider(client, now=lambda: datetime(2026, 8, 26, tzinfo=UTC)).get_card()

    assert card.price == Decimal("2.79")
    assert card.title == "Italian Pasta"
    assert card.observed_at.date().isoformat() == "2026-08-20"


async def test_food_provider_accepts_current_items_response(client_factory):
    def handler(request):
        assert request.url.params["order_by"] == "-date"
        assert request.url.params["size"] == "100"
        assert request.url.params["date__gte"] == "2026-05-28"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": 99,
                        "price": 1,
                        "currency": "EUR",
                        "date": None,
                        "product": {
                            "product_name": "Incomplete",
                            "image_url": "https://images.example/incomplete.jpg",
                        },
                    },
                    {
                        "id": 43,
                        "price": 3.49,
                        "currency": "EUR",
                        "date": "2026-08-25",
                        "product": {
                            "product_name": "French Cheese",
                            "image_url": "https://images.example/cheese.jpg",
                        },
                    }
                ]
            },
        )

    async with client_factory(handler) as client:
        card = await FoodProvider(
            client, now=lambda: datetime(2026, 8, 26, tzinfo=UTC)
        ).get_card()

    assert card.source_id == "43"
