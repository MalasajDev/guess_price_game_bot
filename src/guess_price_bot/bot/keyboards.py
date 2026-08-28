from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def private_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Угадай")],
            [KeyboardButton(text="📈 Больше/меньше")],
            [KeyboardButton(text="🏆 Мои очки")],
        ],
        resize_keyboard=True,
    )


def personal_game_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭️ Скип")]],
        resize_keyboard=True,
    )


def who_closer_join_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎯 Присоединиться", callback_data="who:join")]]
    )


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Угадай", callback_data="mode:guess")],
            [InlineKeyboardButton(text="📈 Больше/меньше", callback_data="mode:more_less")],
            [InlineKeyboardButton(text="🎯 Кто ближе?", callback_data="mode:who_closer")],
            [InlineKeyboardButton(text="🏆 Мои очки", callback_data="score")],
        ]
    )


def category_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Товары", callback_data="category:goods")],
            [InlineKeyboardButton(text="🏠 Недвижимость", callback_data="category:real_estate")],
            [InlineKeyboardButton(text="🚗 Машины", callback_data="category:cars")],
            [InlineKeyboardButton(text="🍔 Еда", callback_data="category:food")],
            [InlineKeyboardButton(text="🎲 Рандом", callback_data="category:random")],
        ]
    )


def currency_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 Гривны", callback_data="currency:UAH")],
            [InlineKeyboardButton(text="🇺🇸 Доллары", callback_data="currency:USD")],
            [InlineKeyboardButton(text="🐷 Рубли", callback_data="currency:RUB")],
        ]
    )


def comparison_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬆️ Больше", callback_data="answer:more"),
                InlineKeyboardButton(text="⬇️ Меньше", callback_data="answer:less"),
            ],
            [InlineKeyboardButton(text="⏭️ Скип", callback_data="skip:personal")],
        ]
    )


def personal_skip_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⏭️ Скип", callback_data="skip:personal")]]
    )


def group_skip_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⏭️ Скип", callback_data="skip:group")]]
    )


def skip_vote_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍", callback_data="skipvote:yes"),
                InlineKeyboardButton(text="👎", callback_data="skipvote:no"),
            ]
        ]
    )


def round_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➡️ Дальше", callback_data="next"),
                InlineKeyboardButton(text="🛑 Стоп", callback_data="stop"),
            ]
        ]
    )
