from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BotCommand, Message

from guess_price_bot.bot.presentation import HELP_TEXT

router = Router(name="help")

BOT_COMMANDS = [
    BotCommand(command="startgame", description="Стартовое меню"),
    BotCommand(command="guessprice", description="Угадай цену"),
    BotCommand(command="biggersmaller", description="Больше или меньше"),
    BotCommand(command="whocloser", description="Кто ближе"),
    BotCommand(command="skip", description="Пропустить карточку"),
    BotCommand(command="score", description="Мои очки"),
    BotCommand(command="rating", description="Рейтинг группы"),
    BotCommand(command="help", description="Список команд"),
]


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(HELP_TEXT)
