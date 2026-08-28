from dataclasses import dataclass
from enum import StrEnum


class GameMode(StrEnum):
    GUESS = "guess"
    MORE_LESS = "more_less"
    WHO_CLOSER = "who_closer"


class Category(StrEnum):
    GOODS = "goods"
    REAL_ESTATE = "real_estate"
    CARS = "cars"
    FOOD = "food"
    RANDOM = "random"

    @classmethod
    def playable(cls) -> tuple["Category", ...]:
        return tuple(category for category in cls if category is not cls.RANDOM)


class Currency(StrEnum):
    UAH = "UAH"
    USD = "USD"
    RUB = "RUB"


@dataclass(frozen=True, slots=True)
class AnswerResult:
    correct: bool
