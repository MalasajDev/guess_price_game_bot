# Guess the Price Bot 🎮

An interactive Telegram game that turns real-world prices into quick, social challenges. Players estimate a price, compete in **Higher or Lower** rounds, and compare scores in private chats or groups.

Built as a production-minded Python service: asynchronous I/O, PostgreSQL persistence, database migrations, structured JSON logs, input validation, and resilient third-party integrations.

## Why it stands out ✨

- **Real data, not hard-coded questions** — products, cars, food, real estate, and exchange rates are fetched from live providers.
- **Two game modes** — classic price guessing with a 15% accuracy window and fast Higher or Lower rounds.
- **Group-ready gameplay** — shared sessions, participant tracking, leaderboards, skip logic, and race-safe state transitions.
- **International pricing** — UAH, USD, and RUB support, with exchange rates cached and refreshed hourly.
- **Operationally ready** — async SQLAlchemy, Alembic migrations, JSON logging, environment-based secrets, test coverage.

## Player flow 🕹️

1. Start a game with `/start`.
2. Choose a category and game mode.
3. Estimate a real price or decide whether the next item costs more or less.
4. Get immediate feedback and compete for the top score with `/score`.

## Tech stack 🧰

| Area                | Technology                                       |
| ------------------- | ------------------------------------------------ |
| Language            | Python 3.12+                                     |
| Telegram            | aiogram 3                                        |
| Database            | PostgreSQL / Supabase, SQLAlchemy async, asyncpg |
| Migrations          | Alembic                                          |
| HTTP & integrations | httpx                                            |
| Configuration       | Pydantic Settings                                |
| Observability       | structlog JSON logs                              |
| Testing             | pytest, pytest-asyncio, respx                    |

## Live data sources 🌍

- **Goods:** SerpApi Google Shopping
- **Cars:** Auto.dev listings
- **Food:** Open Food Facts Open Prices
- **Real estate:** BayutAPI listings
- **Currencies:** Open Exchange Rates
- **Translations:** MyMemory

Provider quotas and terms may change; the bot keeps integrations isolated behind provider adapters so they can be replaced without changing game rules.

## Architecture 🏗️

```text
Telegram updates → aiogram routers → game service → repositories → PostgreSQL
                                  ↘ provider adapters → external price APIs
```

## Run locally 💻

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
Copy-Item .env.example .env
python -m alembic upgrade head
guess-price-bot
```

For macOS/Linux activation, use `source .venv/bin/activate`.

## Configuration 🔐

Copy `.env.example` to `.env` and set the following values. Never commit `.env`.

| Variable                     | Purpose                                                      |
| ---------------------------- | ------------------------------------------------------------ |
| `BOT_TOKEN`                  | Telegram Bot API token from BotFather                        |
| `DATABASE_URL`               | Async PostgreSQL URL, for example `postgresql+asyncpg://...` |
| `SERPAPI_API_KEY`            | SerpApi key for product prices                               |
| `AUTO_DEV_API_KEY`           | Auto.dev key for car listings                                |
| `RAPIDAPI_KEY`               | RapidAPI key for Bayut real-estate data                      |
| `OPEN_EXCHANGE_RATES_APP_ID` | Open Exchange Rates application ID                           |
| `MYMEMORY_CONTACT_EMAIL`     | Optional contact address for translations                    |

## Quality signals ✅

- Async resource lifecycle with orderly shutdown
- Database schema versioning through Alembic
- Structured logs designed for hosted environments
- Secret validation and redaction-aware configuration
- Adversarial and integration tests for state, Telegram, and untrusted remote images
