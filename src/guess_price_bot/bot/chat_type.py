from aiogram.enums import ChatType


def is_private_chat(chat_type: ChatType | str) -> bool:
    return chat_type == ChatType.PRIVATE or chat_type == "private"
