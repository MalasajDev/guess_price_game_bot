import asyncio
import time

import httpx
import structlog
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatPermissions, Message, ReplyKeyboardRemove

from guess_price_bot.bot.chat_type import is_private_chat
from guess_price_bot.bot.keyboards import (
    comparison_menu,
    currency_menu,
    group_skip_menu,
    main_menu,
    personal_game_menu,
    round_menu,
    skip_vote_menu,
)
from guess_price_bot.bot.presentation import (
    API_TOKENS_EXHAUSTED,
    CURRENCY_PROMPT,
    GAME_STOPPED,
    INVALID_PRICE,
    NO_ACTIVE_GAME,
    ONLY_GAME_OWNER,
    PROVIDER_ERROR,
    ROUND_FINISHED,
    ROUND_IN_PROGRESS,
    WRONG_MODE,
    render_answer,
    render_card,
    render_group_miss,
    render_who_closer_answers,
    render_who_closer_winner,
)
from guess_price_bot.bot.runtime import AppContext
from guess_price_bot.domain.models import Category, Currency, GameMode
from guess_price_bot.providers.contracts import ProviderQuotaExceeded, ProviderUnavailable
from guess_price_bot.services.game import AnswerView, RoundView

router = Router(name="game")
logger = structlog.get_logger(__name__)


async def finish_who_closer_after_deadline(app: AppContext, message: Message, chat_id: int) -> None:
    await asyncio.sleep(90)
    async with app.session_factory() as session:
        result = await app.game(session).finish_who_closer_round(chat_id)
    if result is not None:
        await message.bot.send_message(chat_id, render_who_closer_winner(result))
        await message.bot.send_message(chat_id, render_who_closer_answers(result))


async def send_card(message: Message, card: RoundView, _client: httpx.AsyncClient) -> Message:
    started_at = time.perf_counter()
    chat = getattr(message, "chat", None)
    markup = (
        comparison_menu()
        if card.mode is GameMode.MORE_LESS
        else None if chat is None or is_private_chat(chat.type) else group_skip_menu()
    )
    caption = render_card(card)
    try:
        sent = await message.answer_photo(
            photo=card.image_url,
            caption=caption,
            reply_markup=markup,
        )
        logger.info(
            "card_delivered",
            mode="telegram_url",
            total_ms=round((time.perf_counter() - started_at) * 1000, 1),
        )
        if chat is not None and is_private_chat(chat.type):
            await message.answer(
                "⏭️ Для пропуска используйте кнопку ниже.",
                reply_markup=personal_game_menu(),
            )
        return sent
    except TelegramBadRequest:
        logger.info("card_url_rejected", source_url=card.source_url)
        logger.warning("card_image_unavailable", source_url=card.source_url)
        sent = await message.answer(render_card(card, max_length=4096), reply_markup=markup)
        if chat is not None and is_private_chat(chat.type):
            await message.answer(
                "⏭️ Для пропуска используйте кнопку ниже.",
                reply_markup=personal_game_menu(),
            )
        return sent


async def send_result(message: Message, result: AnswerView) -> None:
    await message.answer(render_answer(result), reply_markup=round_menu())
    if result.awarded_points:
        await message.answer("🎉 + 1 балл")


@router.callback_query(F.data.startswith("category:"))
async def select_category(callback: CallbackQuery, app: AppContext) -> None:
    if not callback.message:
        await callback.answer()
        return
    try:
        category = Category(callback.data.removeprefix("category:"))
        async with app.session_factory() as session:
            await app.game(session).select_category(
                callback.from_user.id, category, chat_id=callback.message.chat.id
            )
    except LookupError:
        await callback.answer(NO_ACTIVE_GAME, show_alert=True)
        return
    except PermissionError:
        await callback.answer(ONLY_GAME_OWNER, show_alert=True)
        return
    except ValueError:
        await callback.answer(ROUND_IN_PROGRESS, show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.answer(CURRENCY_PROMPT, reply_markup=currency_menu())


@router.callback_query(F.data.startswith("currency:"))
async def select_currency(callback: CallbackQuery, app: AppContext) -> None:
    try:
        currency = Currency(callback.data.removeprefix("currency:"))
    except ValueError:
        await callback.answer(NO_ACTIVE_GAME, show_alert=True)
        return
    await callback.answer("⏳ Загружаю актуальную цену…")
    if not callback.message:
        return
    try:
        async with app.session_factory() as session:
            game = app.game(session)
            card = await game.select_currency(
                callback.from_user.id, currency, chat_id=callback.message.chat.id
            )
        sent_card = await send_card(callback.message, card, app.http_client)
        async with app.session_factory() as session:
            await app.game(session).set_card_message_id(card.id, sent_card.message_id)
        if card.mode is GameMode.WHO_CLOSER:
            async with app.session_factory() as session:
                players = await app.game(session).open_who_closer_round(
                    callback.message.chat.id, callback.from_user.id
                )
            for player_id, _name in players:
                try:
                    await callback.bot.send_message(player_id, "💭 Напишите предполагаемую цену.")
                except TelegramBadRequest:
                    logger.info("who_closer_private_message_failed", telegram_id=player_id)
            asyncio.create_task(
                finish_who_closer_after_deadline(app, callback.message, callback.message.chat.id)
            )
    except ProviderQuotaExceeded:
        logger.warning("card_provider_quota_exhausted", telegram_id=callback.from_user.id)
        await callback.message.answer(API_TOKENS_EXHAUSTED)
    except ProviderUnavailable:
        logger.exception("card_provider_failed", telegram_id=callback.from_user.id)
        await callback.message.answer(PROVIDER_ERROR)
    except LookupError:
        await callback.message.answer(NO_ACTIVE_GAME)
    except PermissionError:
        await callback.message.answer(ONLY_GAME_OWNER)
    except ValueError:
        await callback.message.answer(ROUND_IN_PROGRESS)


@router.message(F.text & ~F.text.startswith("/") & (F.text != "⏭️ Скип"))
async def price_guess(message: Message, app: AppContext) -> None:
    if message.from_user is None:
        return
    if is_private_chat(message.chat.type):
        try:
            async with app.session_factory() as session:
                accepted = await app.game(session).submit_who_closer_private_answer(
                    message.from_user.id, message.text
                )
        except ValueError:
            await message.answer(INVALID_PRICE)
            return
        except LookupError:
            accepted = None
        if accepted is not None:
            await message.answer(
                "✅ Цена принята!" if accepted else "⚠️ Эту цену уже выбрали. Введите другое число."
            )
            return
    try:
        async with app.session_factory() as session:
            result = await app.game(session).answer_guess(
                message.from_user.id,
                message.text,
                chat_id=message.chat.id,
                display_name=message.from_user.full_name,
                reply_to_message_id=message.reply_to_message.message_id
                if message.reply_to_message
                else None,
            )
    except ValueError as error:
        invalid_price_errors = {"invalid price", "price must be positive and finite"}
        prompt = INVALID_PRICE if str(error) in invalid_price_errors else WRONG_MODE
        await message.answer(prompt)
        return
    except LookupError:
        return
    if result.round_continues:
        await message.answer(render_group_miss())
    else:
        await send_result(message, result)


@router.callback_query(F.data.startswith("answer:"))
async def comparison_answer(callback: CallbackQuery, app: AppContext) -> None:
    if not callback.message:
        await callback.answer()
        return
    direction = callback.data.removeprefix("answer:")
    try:
        async with app.session_factory() as session:
            result = await app.game(session).answer_comparison(
                callback.from_user.id,
                direction,
                chat_id=callback.message.chat.id if callback.message else None,
                display_name=callback.from_user.full_name,
            )
    except PermissionError:
        await callback.answer(ONLY_GAME_OWNER, show_alert=True)
        return
    except (LookupError, ValueError):
        await callback.answer(ROUND_FINISHED, show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await send_result(callback.message, result)


@router.callback_query(F.data == "next")
async def next_round(callback: CallbackQuery, app: AppContext) -> None:
    await callback.answer("⏳ Загружаю новую карточку…")
    if not callback.message:
        return
    try:
        async with app.session_factory() as session:
            card = await app.game(session).next_round(
                callback.from_user.id, chat_id=callback.message.chat.id
            )
        sent_card = await send_card(callback.message, card, app.http_client)
        async with app.session_factory() as session:
            await app.game(session).set_card_message_id(card.id, sent_card.message_id)
    except ProviderQuotaExceeded:
        logger.warning("card_provider_quota_exhausted", telegram_id=callback.from_user.id)
        await callback.message.answer(API_TOKENS_EXHAUSTED)
    except ProviderUnavailable:
        logger.exception("card_provider_failed", telegram_id=callback.from_user.id)
        await callback.message.answer(PROVIDER_ERROR)
    except LookupError:
        await callback.message.answer(NO_ACTIVE_GAME)
    except ValueError:
        await callback.message.answer(ROUND_IN_PROGRESS)
    except PermissionError:
        await callback.message.answer(ONLY_GAME_OWNER)


@router.callback_query(F.data == "stop")
async def stop_game(callback: CallbackQuery, app: AppContext) -> None:
    try:
        async with app.session_factory() as session:
            await app.game(session).stop(
                callback.from_user.id,
                chat_id=callback.message.chat.id if callback.message else None,
            )
    except LookupError:
        await callback.answer(NO_ACTIVE_GAME, show_alert=True)
        return
    except PermissionError:
        await callback.answer(ONLY_GAME_OWNER, show_alert=True)
        return
    await callback.answer()
    if callback.message:
        if is_private_chat(callback.message.chat.type):
            await callback.message.answer(GAME_STOPPED, reply_markup=ReplyKeyboardRemove())
        else:
            await callback.message.answer(GAME_STOPPED, reply_markup=main_menu())


@router.message(Command("skip"))
@router.message(F.text == "⏭️ Скип")
@router.callback_query(F.data == "skip:personal")
async def skip_personal(event: Message | CallbackQuery, app: AppContext) -> None:
    message = event if isinstance(event, Message) else event.message
    user = event.from_user
    if message is None:
        return
    if not is_private_chat(message.chat.type):
        await request_group_skip(event, app)
        return
    try:
        async with app.session_factory() as session:
            result = await app.game(session).skip_personal_round(user.id)
    except (LookupError, PermissionError):
        if isinstance(event, CallbackQuery):
            await event.answer("⚠️ Скип доступен только в личной игре.", show_alert=True)
        else:
            await message.answer("⚠️ Скип доступен только в личной игре.")
        return
    if isinstance(event, CallbackQuery):
        await event.answer()
    symbol = (
        "₴" if result.currency is Currency.UAH else "$" if result.currency is Currency.USD else "₽"
    )
    await message.answer(
        f"⏭️ Вы скипнули карточку!\n\n💰 Реальная цена была: {result.actual_price} {symbol}"
    )
    try:
        async with app.session_factory() as session:
            card = await app.game(session).next_round(user.id)
        await send_card(message, card, app.http_client)
    except ProviderQuotaExceeded:
        await message.answer(API_TOKENS_EXHAUSTED)
    except ProviderUnavailable:
        await message.answer(PROVIDER_ERROR)


VoteKey = tuple[int, int]
skip_votes: dict[VoteKey, dict[int, bool]] = {}
skip_vote_permissions: dict[VoteKey, ChatPermissions | None] = {}


async def close_group_skip_vote(app: AppContext, message: Message, vote_key: VoteKey) -> None:
    await asyncio.sleep(60)
    votes = skip_votes.pop(vote_key, {})
    try:
        if sum(votes.values()) <= len(votes) - sum(votes.values()):
            await message.bot.send_message(
                message.chat.id, "👍 Голосов недостаточно — раунд продолжается."
            )
            return
        try:
            async with app.session_factory() as session:
                result = await app.game(session).skip_group_round(message.chat.id)
        except LookupError:
            return
        await message.bot.send_message(
            message.chat.id,
            f"⏭️ Карточка скипнута!\n\n💰 Реальная цена была: {result.actual_price}",
        )
    finally:
        permissions = skip_vote_permissions.pop(vote_key, None)
        if permissions is not None:
            try:
                await message.bot.set_chat_permissions(message.chat.id, permissions=permissions)
            except TelegramBadRequest:
                logger.exception("skip_vote_permissions_restore_failed", chat_id=message.chat.id)


@router.message(Command("skip"))
@router.callback_query(F.data == "skip:group")
async def request_group_skip(event: Message | CallbackQuery, app: AppContext) -> None:
    message = event if isinstance(event, Message) else event.message
    if message is None or is_private_chat(message.chat.type):
        return
    if isinstance(event, CallbackQuery):
        await event.answer()
    vote = await message.answer(
        "🗳️ Желаете скипнуть карточку? Голосование: 1 минута.", reply_markup=skip_vote_menu()
    )
    vote_key = (message.chat.id, vote.message_id)
    try:
        chat = await message.bot.get_chat(message.chat.id)
        skip_vote_permissions[vote_key] = chat.permissions
        await message.bot.set_chat_permissions(
            message.chat.id, permissions=ChatPermissions(can_send_messages=False)
        )
    except TelegramBadRequest:
        await message.answer(
            "⚠️ Для блокировки сообщений во время голосования выдайте боту право менять разрешения."
        )
    skip_votes[vote_key] = {}
    asyncio.create_task(close_group_skip_vote(app, vote, vote_key))


@router.callback_query(F.data.startswith("skipvote:"))
async def group_skip_vote(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    vote_key = (callback.message.chat.id, callback.message.message_id)
    votes = skip_votes.setdefault(vote_key, {})
    votes[callback.from_user.id] = callback.data.endswith("yes")
    yes = sum(votes.values())
    no = len(votes) - yes
    await callback.answer(f"🗳️ Голоса: 👍 {yes} / 👎 {no}")
