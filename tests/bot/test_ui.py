from decimal import Decimal

from guess_price_bot.bot.keyboards import (
    category_menu,
    currency_menu,
    main_menu,
    personal_game_menu,
    private_main_menu,
    round_menu,
)
from guess_price_bot.bot.presentation import (
    CARD_INTRO,
    CATEGORY_PROMPT,
    CURRENCY_PROMPT,
    INVALID_PRICE,
    render_answer,
    render_card,
)
from guess_price_bot.domain.models import Currency, GameMode
from guess_price_bot.services.game import AnswerView, RoundView


def callback_data(markup):
    return {button.callback_data for row in markup.inline_keyboard for button in row}


def test_menus_have_expected_actions():
    assert callback_data(main_menu()) == {
        "mode:guess",
        "mode:more_less",
        "mode:who_closer",
        "score",
    }
    assert callback_data(category_menu()) == {
        "category:goods",
        "category:real_estate",
        "category:cars",
        "category:food",
        "category:random",
    }
    assert callback_data(currency_menu()) == {"currency:UAH", "currency:USD", "currency:RUB"}
    assert callback_data(round_menu()) == {"next", "stop"}


def test_private_reply_menus_have_expected_buttons():
    assert [button.text for row in private_main_menu().keyboard for button in row] == [
        "🎯 Угадай",
        "📈 Больше/меньше",
        "🏆 Мои очки",
    ]
    assert [button.text for row in personal_game_menu().keyboard for button in row] == ["⏭️ Скип"]


def test_more_less_card_hides_actual_price_and_shows_threshold():
    card = RoundView(
        id="1",
        mode=GameMode.MORE_LESS,
        title="Телефон",
        description="Новый телефон",
        image_url="https://img",
        source_url="https://source",
        displayed_price=Decimal("100"),
        currency=Currency.USD,
        threshold=Decimal("73"),
    )
    caption = render_card(card)
    assert "Телефон" in caption and "Новый телефон" in caption
    assert "73 $" in caption
    assert "100" not in caption


def test_every_static_message_contains_emoji():
    for message in (CARD_INTRO, CATEGORY_PROMPT, CURRENCY_PROMPT):
        assert any(ord(character) > 0xFFFF for character in message)


def test_card_formats_threshold_with_spaces():
    card = RoundView(
        id="1",
        mode=GameMode.MORE_LESS,
        title="Будинок",
        description="",
        image_url="https://img",
        source_url="https://source",
        displayed_price=Decimal("1"),
        currency=Currency.UAH,
        threshold=Decimal("1000000"),
    )
    assert "1 000 000 ₴" in render_card(card)


def test_answer_formats_price_with_spaces():
    answer = AnswerView(
        correct=True,
        actual_price=Decimal("1000000"),
        currency=Currency.UAH,
        awarded_points=1,
        already_resolved=False,
    )
    assert "1 000 000 ₴" in render_answer(answer)


def test_invalid_price_message_explains_allowed_format():
    assert "1 000 000" in INVALID_PRICE and "1000000" in INVALID_PRICE
