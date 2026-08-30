from decimal import Decimal
from html import escape

from guess_price_bot.domain.models import Currency, GameMode
from guess_price_bot.services.game import AnswerView, RoundView, WhoCloserResult

WELCOME = "🎮 Добро пожаловать в игру «Угадай цену»! Выберите режим:"
CATEGORY_PROMPT = "🗂 Выберите категорию:"
CURRENCY_PROMPT = "💱 Выберите вашу валюту: \n\n Russia is a terrorist country!"
CARD_INTRO = "🎯 Ваша карточка готова!"
INVALID_PRICE = (
    "⚠️ Формат цены — только число в формате 1 000 000 или 1000000. Введите положительную цену."
)
GAME_STOPPED = "🛑 Игра остановлена. Возвращайтесь ещё!"
NO_ACTIVE_GAME = "⚠️ Активная игра не найдена. Нажмите /start."
PROVIDER_ERROR = "😔 Сейчас не удалось получить актуальную карточку. Попробуйте ещё раз."
API_TOKENS_EXHAUSTED = "⏳ API-токены, необходимые для игры, закончились. Сыграем через месяц!"
WRONG_MODE = "⚠️ В этом раунде нужно выбрать «Больше» или «Меньше» на кнопках."
ROUND_FINISHED = "⚠️ Этот раунд уже завершён. Нажмите «Следующая карточка»."
ROUND_IN_PROGRESS = "⚠️ Сначала завершите текущий раунд."
ONLY_GAME_OWNER = "⚠️ В режиме «Больше/меньше» отвечает только автор игры."
HELP_TEXT = (
    "📚 Команды бота:\n"
    "/startgame — открыть стартовое меню\n"
    "/guessprice — начать игру «Угадай цену»\n"
    "/biggersmaller — начать игру «Больше/меньше»\n"
    "/whocloser — 🎯 начать игру «Кто ближе?» в группе\n"
    "/skip — ⏭️ пропустить активную карточку\n"
    "/score — показать ваши общие очки\n"
    "/rating — показать рейтинг текущей группы\n"
    "/help — показать эту справку"
)

CURRENCY_SYMBOLS = {
    Currency.UAH: "₴",
    Currency.USD: "$",
    Currency.RUB: "₽",
}


def render_card(card: RoundView, *, max_length: int | None = None) -> str:
    symbol = CURRENCY_SYMBOLS[card.currency]
    details = (
        f"📈 Этот объект стоит больше {format_price(card.threshold)} {symbol}?"
        if card.mode is GameMode.MORE_LESS
        else f"💭 Как вы думаете, сколько это стоит в {symbol}?"
    )
    title = escape(card.title)
    description = escape(card.description)
    source_url = escape(card.source_url, quote=True)

    def build(rendered_title: str, rendered_description: str) -> str:
        return (
            f"{CARD_INTRO}\n\n"
            f"🏷 <b>{rendered_title}</b>\n"
            f"📝 {rendered_description}\n\n"
            f"{details}\n"
            f'🔗 <a href="{source_url}">Источник цены</a>'
        )

    rendered = build(title, description)
    if max_length is None or len(rendered) <= max_length:
        return rendered

    empty_fields_length = len(rendered) - len(title) - len(description)
    field_budget = max(0, max_length - empty_fields_length)
    title_budget = field_budget // 2
    description_budget = field_budget - title_budget
    return build(
        _escaped_prefix(card.title, title_budget),
        _escaped_prefix(card.description, description_budget),
    )


def _escaped_prefix(value: str, limit: int) -> str:
    escaped = escape(value)
    if len(escaped) <= limit:
        return escaped
    if limit <= 1:
        return "…"[:limit]
    low, high = 0, len(value)
    while low < high:
        middle = (low + high + 1) // 2
        if len(escape(value[:middle])) <= limit - 1:
            low = middle
        else:
            high = middle - 1
    return escape(value[:low]) + "…"


def render_answer(answer: AnswerView) -> str:
    symbol = CURRENCY_SYMBOLS[answer.currency]
    status = "✅ Правильно!" if answer.correct else "❌ Неверно."
    return f"{status} Актуальная цена: {format_price(answer.actual_price)} {symbol}."


def render_score(score: int) -> str:
    return f"🏆 Ваши очки: {score}."


def render_group_miss() -> str:
    return "❌ Не угадали. Раунд продолжается — другие участники могут попробовать!"


def render_who_closer_winner(result: WhoCloserResult) -> str:
    symbol = CURRENCY_SYMBOLS[result.currency]
    winner = result.winner_name or "никто"
    return (
        f"🏆 Игрок {escape(winner)} победил!\n\n"
        f"💰 Реальная цена: {format_price(result.actual_price)} {symbol}"
    )


def render_who_closer_answers(result: WhoCloserResult) -> str:
    symbol = CURRENCY_SYMBOLS[result.currency]
    rows = [
        f"• {escape(name)} — "
        f"{'Не ответил' if price is None else format_price(price) + ' ' + symbol}"
        for name, price in result.answers
    ]
    return "📝 Игроки ввели:\n" + "\n".join(rows)


def render_rating(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return "🏆 В этой группе пока нет участников рейтинга."
    lines = [f"{index}. {escape(name)} — {score}" for index, (name, score) in enumerate(rows, 1)]
    return "🏆 Рейтинг группы:\n" + "\n".join(lines)


def format_price(price: Decimal) -> str:
    if price == price.to_integral_value():
        return f"{price:,.0f}".replace(",", " ")
    return f"{price:,.2f}".replace(",", " ")
