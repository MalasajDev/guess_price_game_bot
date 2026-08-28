import asyncio
import os
from contextlib import suppress

import httpx
import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from guess_price_bot.bot.routers import game_router, help_router, score_router, start_router
from guess_price_bot.bot.routers.help import BOT_COMMANDS
from guess_price_bot.bot.runtime import AppContext
from guess_price_bot.config import Settings
from guess_price_bot.db.session import create_engine, create_session_factory
from guess_price_bot.domain.models import Category
from guess_price_bot.health import start_health_server
from guess_price_bot.logging import configure_logging
from guess_price_bot.providers.cars import CarsProvider
from guess_price_bot.providers.exchange_rates import ExchangeRateProvider
from guess_price_bot.providers.food import FoodProvider
from guess_price_bot.providers.goods import GoodsProvider
from guess_price_bot.providers.realty import RealtyProvider
from guess_price_bot.providers.translation import MyMemoryTranslator
from guess_price_bot.services.game import RateCache

logger = structlog.get_logger(__name__)


def reveal(secret_value) -> str:
    return secret_value.get_secret_value()


async def refresh_rates(rate_cache: RateCache) -> None:
    while True:
        try:
            await rate_cache.get(force=True)
            await asyncio.sleep(3600)
        except Exception:
            logger.exception("exchange_rate_refresh_failed")
            await asyncio.sleep(60)


async def main() -> None:
    configure_logging()
    settings = Settings()
    engine = create_engine(reveal(settings.database_url))
    session_factory = create_session_factory(engine)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5, read=15, write=10, pool=5),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=30, keepalive_expiry=30),
    ) as client:
        rates = RateCache(ExchangeRateProvider(client, reveal(settings.open_exchange_rates_app_id)))
        app = AppContext(
            session_factory=session_factory,
            http_client=client,
            providers={
                Category.GOODS: GoodsProvider(client, reveal(settings.serpapi_api_key)),
                Category.CARS: CarsProvider(client, reveal(settings.auto_dev_api_key)),
                Category.FOOD: FoodProvider(client),
                Category.REAL_ESTATE: RealtyProvider(client, reveal(settings.rapidapi_key)),
            },
            translator=MyMemoryTranslator(client, settings.mymemory_contact_email),
            rates=rates,
        )
        bot = Bot(
            token=reveal(settings.bot_token),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dispatcher = Dispatcher()
        dispatcher.include_routers(start_router, score_router, help_router, game_router)
        health_server = await start_health_server(int(os.getenv("PORT", "10000")))
        refresh_task = asyncio.create_task(refresh_rates(rates))
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.set_my_commands(BOT_COMMANDS)
            await dispatcher.start_polling(bot, app=app)
        finally:
            refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await refresh_task
            health_server.close()
            await health_server.wait_closed()
            await bot.session.close()
            await engine.dispose()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
