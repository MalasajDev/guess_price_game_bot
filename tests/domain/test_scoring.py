import random
from decimal import Decimal

import pytest

from guess_price_bot.domain.models import Category
from guess_price_bot.domain.scoring import (
    evaluate_comparison,
    evaluate_guess,
    make_threshold,
    parse_guess,
)


def test_guess_at_35_percent_error_is_correct():
    assert evaluate_guess(Decimal("100"), Decimal("135"), Category.GOODS).correct is True
    assert evaluate_guess(Decimal("100"), Decimal("65"), Category.FOOD).correct is True


def test_guess_over_35_percent_error_is_wrong():
    assert evaluate_guess(Decimal("100"), Decimal("136"), Category.CARS).correct is False


def test_comparison_checks_actual_price():
    assert evaluate_comparison(Decimal("101"), "more", Decimal("100")).correct is True
    assert evaluate_comparison(Decimal("99"), "more", Decimal("100")).correct is False
    assert evaluate_comparison(Decimal("99"), "less", Decimal("100")).correct is True


def test_threshold_is_inside_bounds_and_not_actual():
    for seed in range(50):
        value = make_threshold(Decimal("100"), random.Random(seed))
        assert Decimal("50") <= value <= Decimal("150")
        assert value != Decimal("100")
        assert value == value.to_integral_value()


@pytest.mark.parametrize("text", ["", "0", "-1", "abc", "NaN", "Infinity"])
def test_parse_guess_rejects_invalid_values(text):
    with pytest.raises(ValueError):
        parse_guess(text)


def test_parse_guess_accepts_decimal_comma_and_spaces():
    assert parse_guess(" 1 234,50 ") == Decimal("1234.50")


def test_parse_guess_accepts_grouped_whole_price():
    assert parse_guess("1 000 000") == Decimal("1000000")
