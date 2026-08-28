import asyncio
import time

import httpx

from guess_price_bot.providers.translation import MyMemoryTranslator


async def test_translator_returns_russian_title_and_description(client_factory):
    def handler(request):
        translated = "Камера" if request.url.params["q"] == "Camera" else "Новая камера"
        return httpx.Response(
            200,
            json={"responseStatus": 200, "responseData": {"translatedText": translated}},
        )

    async with client_factory(handler) as client:
        translated = await MyMemoryTranslator(client).translate_card("Camera", "New camera")

    assert translated.title == "Камера"
    assert translated.description == "Новая камера"


async def test_translator_translates_card_fields_concurrently(client_factory):
    async def handler(request):
        await asyncio.sleep(0.05)
        return httpx.Response(
            200,
            json={
                "responseStatus": 200,
                "responseData": {"translatedText": request.url.params["q"]},
            },
        )

    async with client_factory(handler) as client:
        started_at = time.perf_counter()
        await MyMemoryTranslator(client).translate_card("Camera", "New camera")

    assert time.perf_counter() - started_at < 0.09


async def test_translator_returns_original_card_when_api_rate_limits(client_factory):
    def handler(request):
        return httpx.Response(429)

    async with client_factory(handler) as client:
        translated = await MyMemoryTranslator(client).translate_card("Camera", "New camera")

    assert translated.title == "Camera"
    assert translated.description == "New camera"
