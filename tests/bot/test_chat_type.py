from guess_price_bot.bot.chat_type import is_private_chat


def test_private_chat_accepts_aiogram_enum_and_runtime_string():
    assert is_private_chat("private")
    assert not is_private_chat("group")
