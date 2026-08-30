from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from guess_price_bot.bot.presentation import render_rating, render_score
from guess_price_bot.bot.runtime import AppContext

router = Router(name="score")
TELEGRAM_TEXT_LIMIT = 4096


async def get_score(app: AppContext, telegram_id: int) -> int:
    async with app.session_factory() as session:
        return await app.game(session).score(telegram_id)


@router.message(Command("score"))
@router.message(F.text == "🏆 Мои очки")
async def score_command(message: Message, app: AppContext) -> None:
    if message.from_user is None:
        return
    async with app.session_factory() as session:
        score = await app.game(session).score_in_chat(
            message.chat.id, message.from_user.id, message.from_user.full_name
        )
    await message.answer(render_score(score), reply_markup=ReplyKeyboardRemove())


@router.message(Command("rating"))
async def rating_command(message: Message, app: AppContext) -> None:
    if message.from_user is None:
        return
    async with app.session_factory() as session:
        service = app.game(session)
        await service.register_member(
            message.chat.id, message.from_user.id, message.from_user.full_name
        )
        rating = await service.rating(message.chat.id)
    for chunk in _split_message(render_rating(rating)):
        await message.answer(chunk)


def _split_message(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if current and len(current) + len(line) > limit:
            chunks.append(current.rstrip("\n"))
            current = ""
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        current += line
    if current:
        chunks.append(current.rstrip("\n"))
    return chunks or [""]


@router.callback_query(F.data == "score")
async def score_callback(callback: CallbackQuery, app: AppContext) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(render_score(await get_score(app, callback.from_user.id)))
