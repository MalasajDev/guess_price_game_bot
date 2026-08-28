import asyncio
from html import unescape

import httpx

from guess_price_bot.providers.contracts import ProviderUnavailable, TranslatedCard


class MyMemoryTranslator:
    endpoint = "https://api.mymemory.translated.net/get"

    def __init__(self, client: httpx.AsyncClient, contact_email: str | None = None) -> None:
        self.client = client
        self.contact_email = contact_email

    async def translate_card(self, title: str, description: str) -> TranslatedCard:
        translated_title, translated_description = await asyncio.gather(
            self._translate(title), self._translate(description)
        )
        return TranslatedCard(title=translated_title, description=translated_description)

    async def _translate(self, text: str) -> str:
        params = {
            "q": _limit_utf8(text, 500),
            "langpair": "autodetect|ru",
            "mt": "1",
        }
        if self.contact_email:
            params["de"] = self.contact_email
        try:
            response = await self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
            if int(payload.get("responseStatus", 200)) != 200:
                raise ValueError("translation rejected")
            translated = unescape(payload["responseData"]["translatedText"]).strip()
            if not translated:
                raise ValueError("empty translation")
            return translated
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderUnavailable("translation provider unavailable") from error


def _limit_utf8(value: str, maximum: int) -> str:
    encoded = value.encode("utf-8")[:maximum]
    return encoded.decode("utf-8", errors="ignore").strip()
