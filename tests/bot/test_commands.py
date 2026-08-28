from guess_price_bot.bot.presentation import HELP_TEXT, render_group_miss, render_rating
from guess_price_bot.bot.routers.help import BOT_COMMANDS


def test_telegram_command_menu_lists_all_commands():
    assert [item.command for item in BOT_COMMANDS] == [
        "startgame",
        "guessprice",
        "biggersmaller",
        "whocloser",
        "skip",
        "score",
        "rating",
        "help",
    ]


def test_help_explains_all_commands():
    for command in (
        "/startgame",
        "/guessprice",
        "/biggersmaller",
        "/whocloser",
        "/skip",
        "/score",
        "/rating",
        "/help",
    ):
        assert command in HELP_TEXT


def test_group_miss_does_not_reveal_price():
    assert "цена" not in render_group_miss().lower()


def test_rating_is_numbered():
    assert render_rating([("Анна", 5), ("Богдан", 2)]) == (
        "🏆 Рейтинг группы:\n1. Анна — 5\n2. Богдан — 2"
    )
