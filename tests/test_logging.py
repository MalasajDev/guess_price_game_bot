import logging

from guess_price_bot.logging import configure_logging


def test_configure_logging_suppresses_http_client_urls():
    configure_logging()

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
