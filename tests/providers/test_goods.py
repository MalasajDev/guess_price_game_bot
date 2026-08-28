from decimal import Decimal

import httpx
import pytest

from guess_price_bot.providers.contracts import ProviderQuotaExceeded
from guess_price_bot.providers.goods import GoodsProvider


async def test_goods_provider_normalizes_live_offer(client_factory):
    def handler(request):
        assert request.url.params["api_key"] == "secret"
        assert request.url.params["engine"] == "google_shopping"
        assert request.url.params["q"] == "camera"
        return httpx.Response(
            200,
            json={
                "shopping_results": [
                    {
                        "product_id": "12345",
                        "title": "Mirrorless Camera",
                        "extracted_price": 749.99,
                        "thumbnail": "https://images.example/camera.jpg",
                        "product_link": "https://merchant.example/camera",
                        "source": "Camera Store",
                        "snippet": "Digital camera",
                    }
                ]
            },
        )

    async with client_factory(handler) as client:
        card = await GoodsProvider(client, "secret", queries=("camera",)).get_card()

    assert card.price == Decimal("749.99")
    assert card.currency == "USD"
    assert card.source == "serpapi_google_shopping"
    assert card.image_url.endswith("camera.jpg")


async def test_goods_provider_retries_after_timeout(client_factory):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("SerpApi timed out", request=request)
        return httpx.Response(
            200,
            json={
                "shopping_results": [
                    {
                        "product_id": "watch-1",
                        "title": "Smart Watch",
                        "extracted_price": 199,
                        "thumbnail": "https://images.example/watch.jpg",
                        "product_link": "https://merchant.example/watch",
                        "source": "Watch Store",
                    }
                ]
            },
        )

    async with client_factory(handler) as client:
        card = await GoodsProvider(client, "secret", queries=("watch",)).get_card()

    assert card.source_id == "watch-1"
    assert attempts == 2


async def test_goods_provider_reports_exhausted_api_quota(client_factory):
    async with client_factory(lambda request: httpx.Response(429)) as client:
        with pytest.raises(ProviderQuotaExceeded):
            await GoodsProvider(client, "secret").get_card()
