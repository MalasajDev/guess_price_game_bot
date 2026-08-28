from decimal import Decimal

import httpx

from guess_price_bot.providers.realty import RealtyProvider


async def test_bayut_api_normalizes_active_property(client_factory):
    def handler(request):
        assert request.headers["x-rapidapi-key"] == "secret"
        assert request.headers["x-rapidapi-host"] == "uae-real-estate3.p.rapidapi.com"
        assert request.url.params["purpose"] == "for-sale"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "properties": [
                        {
                            "externalID": "7891234",
                            "title": {"en": "Spacious 1BR | Sea View | High Floor"},
                            "price": 1250000,
                            "currency": "AED",
                            "rooms": 1,
                            "baths": 2,
                            "area": 850.5,
                            "coverPhoto": {"url": "https://images.example/home.jpg"},
                            "location": [
                                {"name": "UAE"},
                                {"name": "Dubai"},
                                {"name": "Dubai Marina"},
                            ],
                            "createdAt": 1709251200,
                        }
                    ]
                },
            },
        )

    async with client_factory(handler) as client:
        card = await RealtyProvider(client, "secret").get_card()

    assert card.price == Decimal("1250000")
    assert card.currency == "AED"
    assert "850.5 ft²" in card.description
    assert card.source_url.endswith("details-7891234.html")
