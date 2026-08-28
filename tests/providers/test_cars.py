from decimal import Decimal

import httpx

from guess_price_bot.providers.cars import CarsProvider


def listing_response():
    return {
        "data": [
            {
                "vin": "1FTFW7L83TFA89342",
                "updatedAt": "2026-08-26T12:00:00Z",
                "vehicle": {
                    "year": 2022,
                    "make": "Volvo",
                    "model": "XC60",
                    "trim": "B5",
                },
                "retailListing": {
                    "price": 32990,
                    "miles": 21000,
                    "dealer": "Example Motors",
                    "city": "Austin",
                    "state": "TX",
                    "vdp": "https://dealer.example/car-1",
                    "primaryImage": "https://images.example/car.jpg",
                },
            }
        ]
    }


async def test_auto_dev_normalizes_current_listing(client_factory):
    def handler(request):
        assert request.url.host == "api.auto.dev"
        assert request.headers["authorization"] == "Bearer secret"
        assert request.url.params["limit"] == "20"
        assert "Toyota" in request.url.params["vehicle.make"]
        assert "Kia" in request.url.params["vehicle.make"]
        return httpx.Response(200, json=listing_response())

    async with client_factory(handler) as client:
        card = await CarsProvider(client, "secret").get_card()

    assert card.source == "auto_dev"
    assert card.price == Decimal("32990")
    assert card.title == "2022 Volvo XC60 B5"
    assert "21,000 miles" in card.description
    assert card.image_url == "https://images.example/car.jpg"


async def test_auto_dev_retries_temporary_failure(client_factory):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=listing_response())

    async with client_factory(handler) as client:
        card = await CarsProvider(client, "secret").get_card()

    assert card.source_id == "1FTFW7L83TFA89342"
    assert attempts == 2
