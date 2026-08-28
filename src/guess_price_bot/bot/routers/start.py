import asyncio

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from guess_price_bot.bot.chat_type import is_private_chat
from guess_price_bot.bot.keyboards import (
    category_menu,
    main_menu,
    private_main_menu,
    who_closer_join_menu,
)
from guess_price_bot.bot.presentation import CATEGORY_PROMPT, WELCOME
from guess_price_bot.bot.runtime import AppContext
from guess_price_bot.domain.models import GameMode

router = Router(name="start")
registration_tasks: dict[int, asyncio.Task[None]] = {}


async def close_registration(app: AppContext, bot: Bot, chat_id: int) -> None:
    while True:
        await asyncio.sleep(1)
        async with app.session_factory() as session:
            owner = await app.game(session).activate_who_closer(chat_id)
        if owner is not None:
            await bot.send_message(
                chat_id,
                "⏱️ Регистрация завершена. Создатель, выберите категорию!",
                reply_markup=category_menu(),
            )
            registration_tasks.pop(chat_id, None)
            return


@router.message(CommandStart())
@router.message(Command("startgame"))
async def start_command(message: Message, app: AppContext) -> None:
    if message.from_user is not None and is_private_chat(message.chat.type):
        async with app.session_factory() as session:
            await app.game(session).mark_private_chat(
                message.from_user.id, message.from_user.full_name
            )
    markup = private_main_menu() if is_private_chat(message.chat.type) else main_menu()
    await message.answer(WELCOME, reply_markup=markup)


@router.callback_query(F.data.startswith("mode:"))
async def select_mode(callback: CallbackQuery, app: AppContext) -> None:
    if not callback.message:
        await callback.answer()
        return
    try:
        mode = GameMode(callback.data.removeprefix("mode:"))
        if mode is GameMode.WHO_CLOSER:
            if is_private_chat(callback.message.chat.type):
                await callback.answer("⚠️ Этот режим доступен только в группе.", show_alert=True)
                return
            async with app.session_factory() as session:
                await app.game(session).start_who_closer(
                    callback.from_user.id, callback.from_user.full_name, callback.message.chat.id
                )
            await callback.answer()
            await callback.message.answer(
                "🎯 Идёт регистрация в игру. Время регистрации: 1 минута.",
                reply_markup=who_closer_join_menu(),
            )
            registration_tasks[callback.message.chat.id] = asyncio.create_task(
                close_registration(app, callback.bot, callback.message.chat.id)
            )
            return
        async with app.session_factory() as session:
            await app.game(session).start(
                callback.from_user.id,
                callback.from_user.full_name,
                mode,
                chat_id=callback.message.chat.id,
            )
    except (PermissionError, ValueError):
        await callback.answer("Только владелец игры может начать новую", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        if is_private_chat(callback.message.chat.type):
            await callback.message.answer("🎮 Игра началась!", reply_markup=ReplyKeyboardRemove())
        await callback.message.answer(CATEGORY_PROMPT, reply_markup=category_menu())


async def start_mode(message: Message, app: AppContext, mode: GameMode) -> None:
    if message.from_user is None:
        return
    async with app.session_factory() as session:
        await app.game(session).start(
            message.from_user.id,
            message.from_user.full_name,
            mode,
            chat_id=message.chat.id,
        )
    if is_private_chat(message.chat.type):
        await message.answer("🎮 Игра началась!", reply_markup=ReplyKeyboardRemove())
    await message.answer(CATEGORY_PROMPT, reply_markup=category_menu())


@router.message(Command("guessprice"))
async def guess_price_command(message: Message, app: AppContext) -> None:
    await start_mode(message, app, GameMode.GUESS)


@router.message(Command("biggersmaller"))
async def bigger_smaller_command(message: Message, app: AppContext) -> None:
    await start_mode(message, app, GameMode.MORE_LESS)


@router.message(F.text == "🎯 Угадай")
async def guess_price_menu_button(message: Message, app: AppContext) -> None:
    await start_mode(message, app, GameMode.GUESS)


@router.message(F.text == "📈 Больше/меньше")
async def bigger_smaller_menu_button(message: Message, app: AppContext) -> None:
    await start_mode(message, app, GameMode.MORE_LESS)


@router.message(Command("whocloser"))
async def who_closer_command(message: Message, app: AppContext) -> None:
    if message.from_user is None or is_private_chat(message.chat.type):
        await message.answer("⚠️ 🎯 «Кто ближе?» доступен только в группе.")
        return
    async with app.session_factory() as session:
        await app.game(session).start_who_closer(
            message.from_user.id, message.from_user.full_name, message.chat.id
        )
    await message.answer(
        "🎯 Идёт регистрация в игру. Время регистрации: 1 минута.",
        reply_markup=who_closer_join_menu(),
    )
    registration_tasks[message.chat.id] = asyncio.create_task(
        close_registration(app, message.bot, message.chat.id)
    )


@router.callback_query(F.data == "who:join")
async def join_who_closer(callback: CallbackQuery, app: AppContext) -> None:
    if callback.message is None:
        await callback.answer()
        return
    try:
        async with app.session_factory() as session:
            joined = await app.game(session).join_who_closer(
                callback.from_user.id, callback.from_user.full_name, callback.message.chat.id
            )
    except PermissionError:
        await callback.answer(
            "⚠️ Сначала запустите бота в личных сообщениях: /start", show_alert=True
        )
        return
    except LookupError:
        await callback.answer("⚠️ Регистрация уже завершена.", show_alert=True)
        return
    await callback.answer("✅ Вы уже в игре!" if joined else "ℹ️ Вы уже зарегистрированы.")


@router.message(Command("addtime"))
async def add_who_closer_time(message: Message, app: AppContext) -> None:
    if message.from_user is None:
        return
    try:
        async with app.session_factory() as session:
            added = await app.game(session).add_who_closer_time(
                message.from_user.id, message.chat.id
            )
    except LookupError:
        return
    await message.answer(
        "⏱️ Регистрация продлена на 30 секунд!" if added else "⚠️ Время уже добавлено."
    )
