from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from guess_price_bot.domain.models import Category
from guess_price_bot.providers.contracts import ListingProvider, Translator
from guess_price_bot.services.game import GameService, RateCache


@dataclass(frozen=True, slots=True)
class AppContext:
    session_factory: async_sessionmaker[AsyncSession]
    http_client: httpx.AsyncClient
    providers: dict[Category, ListingProvider]
    translator: Translator
    rates: RateCache

    def game(self, session: AsyncSession) -> GameService:
        return GameService(
            session=session,
            providers=self.providers,
            translator=self.translator,
            rates=self.rates,
        )
