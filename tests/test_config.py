from guess_price_bot.config import Settings


def test_settings_reads_required_environment(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")
    monkeypatch.setenv("SERPAPI_API_KEY", "serpapi")
    monkeypatch.setenv("AUTO_DEV_API_KEY", "auto-dev-key")
    monkeypatch.setenv("RAPIDAPI_KEY", "rapid-key")
    monkeypatch.setenv("OPEN_EXCHANGE_RATES_APP_ID", "rates")

    settings = Settings(_env_file=None)

    assert settings.bot_token.get_secret_value() == "token"
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")
    assert settings.serpapi_api_key.get_secret_value() == "serpapi"


def test_settings_rejects_missing_required_environment(monkeypatch):
    for name in (
        "BOT_TOKEN",
        "DATABASE_URL",
        "SERPAPI_API_KEY",
        "AUTO_DEV_API_KEY",
        "RAPIDAPI_KEY",
        "OPEN_EXCHANGE_RATES_APP_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    try:
        Settings(_env_file=None)
    except ValueError:
        return
    raise AssertionError("Settings must reject missing secrets")
