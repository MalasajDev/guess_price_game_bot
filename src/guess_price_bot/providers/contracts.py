from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol


class ProviderUnavailable(RuntimeError):
    """Raised when a provider cannot return a valid card."""


class ProviderQuotaExceeded(ProviderUnavailable):
    """Raised when an API provider has no remaining request quota."""


@dataclass(frozen=True, slots=True)
class ListingCard:
    source: str
    source_id: str
    title: str
    description: str
    price: Decimal
    currency: str
    image_url: str
    source_url: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class TranslatedCard:
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class RateSnapshot:
    rates: dict[str, Decimal]
    provider_at: datetime
    fetched_at: datetime

    def convert(self, amount: Decimal, source: str, target: str) -> Decimal:
        try:
            source_rate = self.rates[source.upper()]
            target_rate = self.rates[target.upper()]
        except KeyError as error:
            raise ProviderUnavailable(f"unsupported currency: {error.args[0]}") from error
        return (amount / source_rate * target_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


class ListingProvider(Protocol):
    async def get_card(self) -> ListingCard: ...


class Translator(Protocol):
    async def translate_card(self, title: str, description: str) -> TranslatedCard: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


def decimal_price(value: object) -> Decimal:
    try:
        price = Decimal(str(value))
    except Exception as error:
        raise ProviderUnavailable("invalid provider price") from error
    if not price.is_finite() or price <= 0:
        raise ProviderUnavailable("provider price must be positive")
    return price
