import math
import random
from decimal import Decimal, InvalidOperation

from guess_price_bot.domain.models import AnswerResult, Category

MAX_GUESS_ERROR = Decimal("0.30")


def parse_guess(text: str) -> Decimal:
    normalized = text.strip().replace(" ", "").replace(",", ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError("invalid price") from error
    if not value.is_finite() or value <= 0:
        raise ValueError("price must be positive and finite")
    return value


def evaluate_guess(actual: Decimal, guess: Decimal, category: Category) -> AnswerResult:
    if actual <= 0 or not actual.is_finite():
        raise ValueError("actual price must be positive and finite")
    return AnswerResult(correct=abs(guess - actual) / actual <= MAX_GUESS_ERROR)


def evaluate_comparison(actual: Decimal, direction: str, threshold: Decimal) -> AnswerResult:
    if direction == "more":
        return AnswerResult(correct=actual > threshold)
    if direction == "less":
        return AnswerResult(correct=actual < threshold)
    raise ValueError("direction must be 'more' or 'less'")


def make_threshold(actual: Decimal, rng: random.Random) -> Decimal:
    lower = math.ceil(actual * Decimal("0.5"))
    upper = math.floor(actual * Decimal("1.5"))
    candidates = [value for value in range(lower, upper + 1) if Decimal(value) != actual]
    if not candidates:
        raise ValueError("price is too small to create a distinct whole threshold")
    return Decimal(rng.choice(candidates))
