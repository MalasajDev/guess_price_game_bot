from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr
    database_url: SecretStr
    serpapi_api_key: SecretStr
    auto_dev_api_key: SecretStr
    rapidapi_key: SecretStr
    open_exchange_rates_app_id: SecretStr
    mymemory_contact_email: str | None = None

    @field_validator(
        "bot_token",
        "database_url",
        "serpapi_api_key",
        "auto_dev_api_key",
        "rapidapi_key",
        "open_exchange_rates_app_id",
    )
    @classmethod
    def required_secret_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("required setting must not be blank")
        return value
