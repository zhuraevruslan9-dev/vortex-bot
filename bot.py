import os
import asyncio
import logging
import base64
from datetime import datetime

import aiohttp
import aiosqlite
from openai import OpenAI

from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

DB_NAME = "vortex.db"

DEFAULT_THRESHOLD = 2.0
PRICE_CHECK_INTERVAL = 300  # 5 минут

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в переменных окружения")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не найден в переменных окружения")

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("vortex")


# ============================================================
# TRANSLATIONS
# ============================================================

T = {
    "ru": {
        "welcome": (
            "👋 Добро пожаловать в Vortex!\n\n"
            "📊 Отслеживай криптовалюты и акции\n"
            "⭐ Создавай избранное\n"
            "🔔 Настраивай уведомления\n"
            "🤖 Общайся с AI\n"
            "🖼 Анализируй графики\n"
            "💼 Используй виртуальный портфель\n\n"
            "⚠️ Виртуальный портфель предназначен только для обучения "
            "и не совершает реальные сделки."
        ),

        "choose_lang": "🌍 Выберите язык:",

        "menu": "🏠 Главное меню:",

        "track": "📈 Выберите актив:",

        "choose_type": "Выберите тип актива:",

        "type_changed": "✅ Тип актива изменён.",

        "lang_changed": "✅ Язык изменён.",

        "back": "◀️ Назад",

        "settings": "⚙️ Настройки",

        "set_lang": "🌍 Сменить язык",

        "set_type": "📊 Тип активов",

        "btn_track": "⭐ Мои активы",

        "btn_market": "📊 Рыночный обзор",

        "btn_chart": "🖼 Анализ графика",

        "btn_ai": "🤖 AI Помощник",

        "btn_portfolio": "💼 Виртуальный портфель",

        "btn_history": "📜 История сигналов",

        "btn_settings": "⚙️ Настройки",

        "type_crypto": "💎 Криптовалюты",

        "type_stocks": "📈 Акции",

        "empty_watchlist": (
            "⭐ Избранное пока пустое.\n\n"
            "Нажми «Добавить актив», чтобы начать."
        ),

        "add_asset": "➕ Добавить актив",

        "remove_asset": "🗑 Удалить",

        "asset_added": "⭐ {name} добавлен в избранное.",

        "asset_removed": "🗑 {name} удалён из избранного.",

        "already_added": "Этот актив уже есть в избранном.",

        "asset_card": (
            "{emoji} <b>{name}</b> ({ticker})\n\n"
            "💰 Цена: <b>${price:,.2f}</b>\n"
            "📊 Изменение 24ч: <b>{change:+.2f}%</b>\n\n"
            "🔔 Порог уведомления: <b>{threshold:.2f}%</b>"
        ),

        "threshold": (
            "🔔 Выберите порог уведомления для <b>{name}</b>:"
        ),

        "threshold_saved": (
            "✅ Порог для <b>{name}</b> установлен: <b>{threshold:.2f}%</b>"
        ),

        "market": "📊 <b>Рыночный обзор</b>\n\n",

        "history_empty": "📜 История сигналов пока пустая.",

        "history_title": "📜 <b>Последние сигналы</b>\n\n",

        "chart": (
            "🖼 Отправь мне скриншот графика.\n\n"
            "Я попробую определить:\n"
            "• направление тренда\n"
            "• уровни поддержки/сопротивления\n"
            "• возможные сценарии\n"
            "• риски\n\n"
            "⚠️ Анализ AI не является гарантией движения цены."
        ),

        "analyzing": "🔍 Анализирую график...",

        "ai": (
            "🤖 Задай мне вопрос.\n\n"
            "Например:\n"
            "• Что такое Bitcoin?\n"
            "• Объясни RSI простыми словами\n"
            "• Чем акция отличается от облигации?\n"
            "• Что означает высокий объём торгов?"
        ),

        "ai_error": (
            "😕 AI временно недоступен. Попробуй немного позже."
        ),

        "server_error": "⚠️ Не удалось получить данные. Попробуйте позже.",

        "blocked": (
            "Извини, я не могу помочь с этим запросом. "
            "Давай поговорим об IT, финансах или анализе рынка."
        ),

        "unknown": (
            "Я не понял запрос.\n\n"
            "Можно выбрать действие в меню или написать тикер, "
            "например BTC, ETH, AAPL или NVDA."
        ),

        "portfolio_empty": (
            "💼 Виртуальный портфель пуст.\n\n"
            "Добавь виртуальную позицию через кнопку ниже."
        ),

        "portfolio": "💼 <b>Виртуальный портфель</b>\n\n",

        "add_virtual": "➕ Добавить позицию",

        "portfolio_help": (
            "Напиши в формате:\n\n"
            "<code>BTC 1000</code>\n\n"
            "Это означает: виртуально вложить $1000 в BTC.\n\n"
            "⚠️ Это только симуляция. Реальные деньги не используются."
        ),

        "position_added": (
            "✅ Виртуальная позиция добавлена.\n\n"
            "{name}: ${amount:,.2f}"
        ),

        "virtual_only": (
            "💡 Это виртуальный портфель. "
            "Он не подключён к бирже и не совершает реальные операции."
        ),
    },

    "en": {
        "welcome": (
            "👋 Welcome to Vortex!\n\n"
            "📊 Track crypto and stocks\n"
            "⭐ Build a watchlist\n"
            "🔔 Set alerts\n"
            "🤖 Ask AI\n"
            "🖼 Analyze charts\n"
            "💼 Use a virtual portfolio\n\n"
            "⚠️ The virtual portfolio is for education only."
        ),

        "choose_lang": "🌍 Choose language:",

        "menu": "🏠 Main menu:",

        "track": "📈 Choose an asset:",

        "choose_type": "Choose asset type:",

        "type_changed": "✅ Asset type changed.",

        "lang_changed": "✅ Language changed.",

        "back": "◀️ Back",

        "settings": "⚙️ Settings",

        "set_lang": "🌍 Change language",

        "set_type": "📊 Asset type",

        "btn_track": "⭐ My assets",

        "btn_market": "📊 Market overview",

        "btn_chart": "🖼 Chart analysis",

        "btn_ai": "🤖 AI Assistant",

        "btn_portfolio": "💼 Virtual portfolio",

        "btn_history": "📜 Signal history",

        "btn_settings": "⚙️ Settings",

        "type_crypto": "💎 Crypto",

        "type_stocks": "📈 Stocks",

        "empty_watchlist": (
            "⭐ Your watchlist is empty.\n\n"
            "Press Add asset to begin."
        ),

        "add_asset": "➕ Add asset",

        "remove_asset": "🗑 Remove",

        "asset_added": "⭐ {name} added to watchlist.",

        "asset_removed": "🗑 {name} removed.",

        "already_added": "This asset is already in your watchlist.",

        "asset_card": (
            "{emoji} <b>{name}</b> ({ticker})\n\n"
            "💰 Price: <b>${price:,.2f}</b>\n"
            "📊 24h change: <b>{change:+.2f}%</b>\n\n"
            "🔔 Alert threshold: <b>{threshold:.2f}%</b>"
        ),

        "threshold": (
            "🔔 Choose alert threshold for <b>{name}</b>:"
        ),

        "threshold_saved": (
            "✅ Threshold for <b>{name}</b>: <b>{threshold:.2f}%</b>"
        ),

        "market": "📊 <b>Market overview</b>\n\n",

        "history_empty": "📜 Signal history is empty.",

        "history_title": "📜 <b>Recent signals</b>\n\n",

        "chart": (
            "🖼 Send me a chart screenshot.\n\n"
            "I will try to identify:\n"
            "• trend\n"
            "• support/resistance\n"
            "• possible scenarios\n"
            "• risks\n\n"
            "⚠️ AI analysis cannot guarantee price movements."
        ),

        "analyzing": "🔍 Analyzing chart...",

        "ai": (
            "🤖 Ask me a question.\n\n"
            "For example:\n"
            "• What is Bitcoin?\n"
            "• Explain RSI simply\n"
            "• What is a stock?\n"
            "• What does high trading volume mean?"
        ),

        "ai_error": "😕 AI is temporarily unavailable.",

        "server_error": "⚠️ Could not get market data.",

        "blocked": (
            "Sorry, I can't help with that request. "
            "Let's talk about IT, finance or market analysis."
        ),

        "unknown": (
            "I didn't understand.\n\n"
            "Try a ticker such as BTC, ETH, AAPL or NVDA."
        ),

        "portfolio_empty": (
            "💼 Your virtual portfolio is empty."
        ),

        "portfolio": "💼 <b>Virtual portfolio</b>\n\n",

        "add_virtual": "➕ Add position",

        "portfolio_help": (
            "Send:\n\n"
            "<code>BTC 1000</code>\n\n"
            "This simulates investing $1000 in BTC.\n\n"
            "⚠️ Simulation only."
        ),

        "position_added": (
            "✅ Virtual position added.\n\n"
            "{name}: ${amount:,.2f}"
        ),

        "virtual_only": (
            "💡 This is a virtual portfolio. "
            "It does not connect to an exchange."
        ),
    }
}


# ============================================================
# ASSETS
# ============================================================

CRYPTO = {
    "BTCUSDT": {
        "name": "Bitcoin",
        "emoji": "₿",
        "aliases": ["bitcoin", "btc", "биткоин", "биток"],
    },
    "ETHUSDT": {
        "name": "Ethereum",
        "emoji": "Ξ",
        "aliases": ["ethereum", "eth", "эфириум", "эфир"],
    },
    "BNBUSDT": {
        "name": "BNB",
        "emoji": "🟡",
        "aliases": ["bnb", "бнб", "binance coin"],
    },
    "SOLUSDT": {
        "name": "Solana",
        "emoji": "🟣",
        "aliases": ["solana", "sol", "солана"],
    },
    "XRPUSDT": {
        "name": "XRP",
        "emoji": "⚡",
        "aliases": ["xrp", "рипл", "ripple"],
    },
    "ADAUSDT": {
        "name": "Cardano",
        "emoji": "🔵",
        "aliases": ["cardano", "ada", "кардано"],
    },
    "DOGEUSDT": {
        "name": "Dogecoin",
        "emoji": "🐕",
        "aliases": ["dogecoin", "doge", "доге", "догикоин"],
    },
    "DOTUSDT": {
        "name": "Polkadot",
        "emoji": "⚪",
        "aliases": ["polkadot", "dot", "полкадот"],
    },
    "AVAXUSDT": {
        "name": "Avalanche",
        "emoji": "🔺",
        "aliases": ["avalanche", "avax", "аваланч"],
    },
    "LINKUSDT": {
        "name": "Chainlink",
        "emoji": "🔗",
        "aliases": ["chainlink", "link", "чейнлинк"],
    },
}

STOCKS = {
    "AAPL": {
        "name": "Apple",
        "emoji": "🍎",
        "aliases": ["apple", "aapl", "эпл", "аппл"],
    },
    "TSLA": {
        "name": "Tesla",
        "emoji": "🚗",
        "aliases": ["tesla", "tsla", "тесла"],
    },
    "GOOGL": {
        "name": "Alphabet",
        "emoji": "🔎",
        "aliases": ["google", "googl", "гугл"],
    },
    "AMZN": {
        "name": "Amazon",
        "emoji": "📦",
        "aliases": ["amazon", "amzn", "амазон"],
    },
    "MSFT": {
        "name": "Microsoft",
        "emoji": "🪟",
        "aliases": ["microsoft", "msft", "майкрософт"],
    },
    "NVDA": {
        "name": "NVIDIA",
        "emoji": "🟢",
        "aliases": ["nvidia", "nvda", "нвидиа"],
    },
    "META": {
        "name": "Meta",
        "emoji": "🔵",
        "aliases": ["meta", "мета", "facebook"],
    },
    "NFLX": {
        "name": "Netflix",
        "emoji": "🎬",
        "aliases": ["netflix", "nflx", "нетфликс"],
    },
    "AMD": {
        "name": "AMD",
        "emoji": "🔴",
        "aliases": ["amd", "эйэмди"],
    },
    "BABA": {
        "name": "Alibaba",
        "emoji": "🛒",
        "aliases": ["alibaba", "baba", "алибаба"],
    },
}


# ============================================================
# SIMPLE CONTENT FILTER
# ============================================================

BLOCKED = [
    "порно",
    "порнуха",
    "xxx",
    "ххх",
    "нюдс",
    "nude",
    "naked",
    "nsfw",
    "sex",
    "секс",
    "эротика",
    "hentai",
    "хентай",
]


def is_blocked(text: str) -> bool:
    text = text.lower()
    return any(word in text for word in BLOCKED)


# ============================================================
# DATABASE
# ============================================================

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                lang TEXT DEFAULT 'ru',
                type TEXT DEFAULT 'crypto',
                chat_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                threshold REAL DEFAULT 2.0,
                last_price REAL,
                UNIQUE(user_id, asset)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                old_price REAL,
                new_price REAL,
                change_percent REAL,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS virtual_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                invested REAL NOT NULL,
                quantity REAL NOT NULL,
                buy_price REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await db.commit()


async def ensure_user(user_id: int, chat_id: int | None = None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, chat_id)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET chat_id = COALESCE(excluded.chat_id, users.chat_id)
        """, (user_id, chat_id))

        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT user_id, lang, type, chat_id
            FROM users
            WHERE user_id = ?
        """, (user_id,))

        return await cur.fetchone()


async def set_lang(user_id: int, lang: str):
    await ensure_user(user_id)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET lang=? WHERE user_id=?",
            (lang, user_id)
        )
        await db.commit()


async def set_type(user_id: int, asset_type: str):
    await ensure_user(user_id)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET type=? WHERE user_id=?",
            (asset_type, user_id)
        )
        await db.commit()


# ============================================================
# WATCHLIST
# ============================================================

async def add_watchlist(
    user_id: int,
    asset: str,
    threshold: float = DEFAULT_THRESHOLD
):
    await ensure_user(user_id)

    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute("""
                INSERT INTO watchlist
                (user_id, asset, threshold)
                VALUES (?, ?, ?)
            """, (user_id, asset, threshold))

            await db.commit()
            return True

        except aiosqlite.IntegrityError:
            return False


async def remove_watchlist(user_id: int, asset: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            DELETE FROM watchlist
            WHERE user_id=? AND asset=?
        """, (user_id, asset))

        await db.commit()


async def get_watchlist(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT asset, threshold, last_price
            FROM watchlist
            WHERE user_id=?
            ORDER BY id DESC
        """, (user_id,))

        return await cur.fetchall()


async def get_watch_item(user_id: int, asset: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT asset, threshold, last_price
            FROM watchlist
            WHERE user_id=? AND asset=?
        """, (user_id, asset))

        return await cur.fetchone()


async def update_last_price(
    user_id: int,
    asset: str,
    price: float
):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE watchlist
            SET last_price=?
            WHERE user_id=? AND asset=?
        """, (price, user_id, asset))

        await db.commit()


async def set_threshold(
    user_id: int,
    asset: str,
    threshold: float
):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE watchlist
            SET threshold=?
            WHERE user_id=? AND asset=?
        """, (threshold, user_id, asset))

        await db.commit()


async def get_all_watchlist():
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT user_id, asset, threshold, last_price
            FROM watchlist
        """)

        return await cur.fetchall()


# ============================================================
# SIGNAL HISTORY
# ============================================================

async def add_signal(
    user_id,
    asset,
    old_price,
    new_price,
    change_percent
):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO signals
            (user_id, asset, old_price, new_price,
             change_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            asset,
            old_price,
            new_price,
            change_percent,
            datetime.utcnow().isoformat()
        ))

        await db.commit()


async def get_signals(user_id, limit=10):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT asset, old_price, new_price,
                   change_percent, created_at
            FROM signals
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit))

        return await cur.fetchall()


# ============================================================
# VIRTUAL PORTFOLIO
# ============================================================

async def add_virtual_position(
    user_id,
    asset,
    invested,
    quantity,
    buy_price
):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO virtual_positions
            (user_id, asset, invested, quantity, buy_price, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            asset,
            invested,
            quantity,
            buy_price,
            datetime.utcnow().isoformat()
        ))

        await db.commit()


async def get_virtual_positions(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT asset, invested, quantity, buy_price
            FROM virtual_positions
            WHERE user_id=?
            ORDER BY id DESC
        """, (user_id,))

        return await cur.fetchall()


# ============================================================
# ASSET HELPERS
# ============================================================

def get_asset_data(asset):
    if asset in CRYPTO:
        return CRYPTO[asset], "crypto"

    if asset in STOCKS:
        return STOCKS[asset], "stock"

    return None, None


def find_asset(text):
    value = text.lower().strip()

    for symbol, data in CRYPTO.items():
        if (
            value == symbol.lower()
            or value == symbol.lower().replace("usdt", "")
            or value in data["aliases"]
        ):
            return "crypto", symbol, data

    for symbol, data in STOCKS.items():
        if (
            value == symbol.lower()
            or value in data["aliases"]
        ):
            return "stock", symbol, data

    return None


# ============================================================
# MARKET API
# ============================================================

async def get_crypto(symbol):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": symbol},
            timeout=15
        ) as response:

            response.raise_for_status()

            data = await response.json()

            return {
                "price": float(data["lastPrice"]),
                "change": float(data["priceChangePercent"]),
                "volume": float(data["volume"]),
            }


async def get_stock(symbol):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?interval=1d&range=1d"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        ) as response:

            response.raise_for_status()

            data = await response.json()

            result = data["chart"]["result"][0]
            meta = result["meta"]

            price = float(meta["regularMarketPrice"])

            previous = (
                meta.get("previousClose")
                or meta.get("chartPreviousClose")
                or price
            )

            previous = float(previous)

            change = (
                (price - previous) / previous * 100
                if previous
                else 0
            )

            return {
                "price": price,
                "change": change,
                "volume": None,
            }


async def get_market_data(asset):
    _, asset_type = get_asset_data(asset)

    if asset_type == "crypto":
        return await get_crypto(asset)

    if asset_type == "stock":
        return await get_stock(asset)

    raise ValueError("Unknown asset")


# ============================================================
# AI
# ============================================================

def ai_text(prompt):
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    return response.output_text


def ai_image(prompt, image_b64):
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            "data:image/jpeg;base64,"
                            + image_b64
                        ),
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    return response.output_text


def ai_asset_analysis(
    name,
    ticker,
    price,
    change,
    lang
):
    if lang == "ru":
        prompt = f"""
Ты — AI-аналитик учебного приложения Vortex.

Актив:
{name} ({ticker})

Текущая цена:
${price:,.2f}

Изменение за 24 часа:
{change:+.2f}%

Сделай краткий образовательный анализ.

Структура:

📌 Что происходит
📈 Позитивный сценарий
📉 Негативный сценарий
⚠️ Основные риски
🔎 Что стоит отслеживать

Не говори пользователю просто "покупай" или "продавай".
Не выдавай прогноз как гарантированный факт.

Пиши понятно и кратко.
"""

    else:
        prompt = f"""
You are the educational AI analyst of Vortex.

Asset:
{name} ({ticker})

Price:
${price:,.2f}

24h change:
{change:+.2f}%

Give a short educational analysis.

Structure:

📌 What is happening
📈 Positive scenario
📉 Negative scenario
⚠️ Main risks
🔎 What to watch

Do not simply tell the user to buy or sell.
Do not present predictions as guaranteed facts.

Keep it concise.
"""

    return ai_text(prompt)


# ============================================================
# KEYBOARDS
# ============================================================

def main_kb(lang):
    return ReplyKeyboardMarkup(
        [
            [T[lang]["btn_track"]],
            [T[lang]["btn_market"]],
            [T[lang]["btn_chart"]],
            [T[lang]["btn_ai"]],
            [T[lang]["btn_portfolio"]],
            [T[lang]["btn_history"]],
            [T[lang]["btn_settings"]],
        ],
        resize_keyboard=True
    )


def back_kb(lang):
    return ReplyKeyboardMarkup(
        [[T[lang]["back"]]],
        resize_keyboard=True
    )


def lang_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🇷🇺 Русский",
                callback_data="lang_ru"
            ),
            InlineKeyboardButton(
                "🇺🇸 English",
                callback_data="lang_en"
            ),
        ]
    ])


def type_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💎 Крипта / Crypto",
                callback_data="type_crypto"
            ),
            InlineKeyboardButton(
                "📈 Акции / Stocks",
                callback_data="type_stocks"
            ),
        ]
    ])


def asset_kb(asset_type):
    source = CRYPTO if asset_type == "crypto" else STOCKS

    buttons = []
    row = []

    for symbol, data in source.items():
        row.append(
            InlineKeyboardButton(
                data["name"],
                callback_data=f"add_{symbol}"
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)


def threshold_kb(asset):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "0.5%",
                callback_data=f"thr_{asset}_0.5"
            ),
            InlineKeyboardButton(
                "1%",
                callback_data=f"thr_{asset}_1"
            ),
            InlineKeyboardButton(
                "2%",
                callback_data=f"thr_{asset}_2"
            ),
        ],
        [
            InlineKeyboardButton(
                "3%",
                callback_data=f"thr_{asset}_3"
            ),
            InlineKeyboardButton(
                "5%",
                callback_data=f"thr_{asset}_5"
            ),
            InlineKeyboardButton(
                "10%",
                callback_data=f"thr_{asset}_10"
            ),
        ],
    ])


def watchlist_kb(items):
    buttons = []

    for asset, threshold, _ in items:
        data, _ = get_asset_data(asset)

        if not data:
            continue

        buttons.append([
            InlineKeyboardButton(
                f"{data['emoji']} {data['name']}",
                callback_data=f"view_{asset}"
            ),
            InlineKeyboardButton(
                "🗑",
                callback_data=f"remove_{asset}"
            ),
        ])

    buttons.append([
        InlineKeyboardButton(
            "➕ Добавить актив",
            callback_data="choose_asset"
        )
    ])

    return InlineKeyboardMarkup(buttons)


def asset_card_kb(asset):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔔 Порог",
                callback_data=f"threshold_{asset}"
            ),
            InlineKeyboardButton(
                "🗑 Удалить",
                callback_data=f"remove_{asset}"
            ),
        ]
    ])


def portfolio_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Добавить позицию",
                callback_data="virtual_add"
            )
        ]
    ])


# ============================================================
# /START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id
    cid = update.effective_chat.id

    await ensure_user(uid, cid)

    row = await get_user(uid)

    if not row or not row[1]:
        await update.message.reply_text(
            T["ru"]["choose_lang"],
            reply_markup=lang_kb()
        )
        return

    lang = row[1]

    await update.message.reply_text(
        T[lang]["welcome"],
        reply_markup=main_kb(lang)
    )


# ============================================================
# LANGUAGE
# ============================================================

async def cb_lang(update, context):

    query = update.callback_query

    await query.answer()

    lang = query.data.replace("lang_", "")
    uid = query.from_user.id

    await set_lang(uid, lang)

    await query.message.reply_text(
        T[lang]["lang_changed"],
        reply_markup=main_kb(lang)
    )


# ============================================================
# TYPE
# ============================================================

async def cb_type(update, context):

    query = update.callback_query

    await query.answer()

    asset_type = query.data.replace("type_", "")
    uid = query.from_user.id

    await set_type(uid, asset_type)

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    await query.message.reply_text(
        T[lang]["type_changed"],
        reply_markup=main_kb(lang)
    )


# ============================================================
# WATCHLIST
# ============================================================

async def show_watchlist(update, context):

    uid = update.effective_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    items = await get_watchlist(uid)

    if not items:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    T[lang]["add_asset"],
                    callback_data="choose_asset"
                )
            ]
        ])

        await update.message.reply_text(
            T[lang]["empty_watchlist"],
            reply_markup=keyboard
        )

        return

    await update.message.reply_text(
        "⭐ <b>Мои активы</b>",
        reply_markup=watchlist_kb(items),
        parse_mode="HTML"
    )


async def choose_asset(update, context):

    query = update.callback_query

    await query.answer()

    uid = query.from_user.id

    row = await get_user(uid)

    lang = row[1] if row else "ru"
    asset_type = row[2] if row else "crypto"

    await query.message.reply_text(
        T[lang]["track"],
        reply_markup=asset_kb(asset_type)
    )


async def cb_add_asset(update, context):

    query = update.callback_query

    await query.answer()

    asset = query.data.replace("add_", "")
    uid = query.from_user.id

    data, _ = get_asset_data(asset)

    if not data:
        return

    success = await add_watchlist(
        uid,
        asset,
        DEFAULT_THRESHOLD
    )

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    if not success:
        await query.message.reply_text(
            T[lang]["already_added"]
        )
        return

    try:
        market = await get_market_data(asset)

        await update_last_price(
            uid,
            asset,
            market["price"]
        )

    except Exception:
        logger.exception("Failed to fetch initial price")

    await query.message.reply_text(
        T[lang]["asset_added"].format(
            name=data["name"]
        )
    )


async def cb_remove_asset(update, context):

    query = update.callback_query

    await query.answer()

    asset = query.data.replace("remove_", "")
    uid = query.from_user.id

    data, _ = get_asset_data(asset)

    await remove_watchlist(uid, asset)

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    await query.message.reply_text(
        T[lang]["asset_removed"].format(
            name=data["name"] if data else asset
        )
    )


# ============================================================
# ASSET CARD
# ============================================================

async def cb_view_asset(update, context):

    query = update.callback_query

    await query.answer()

    asset = query.data.replace("view_", "")
    uid = query.from_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    item = await get_watch_item(uid, asset)

    if not item:
        await query.message.reply_text(
            T[lang]["unknown"]
        )
        return

    data, _ = get_asset_data(asset)

    try:
        market = await get_market_data(asset)

        text = T[lang]["asset_card"].format(
            emoji=data["emoji"],
            name=data["name"],
            ticker=asset,
            price=market["price"],
            change=market["change"],
            threshold=item[1],
        )

        await query.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=asset_card_kb(asset)
        )

    except Exception:
        logger.exception("Asset card error")

        await query.message.reply_text(
            T[lang]["server_error"]
        )


# ============================================================
# THRESHOLD
# ============================================================

async def cb_threshold(update, context):

    query = update.callback_query

    await query.answer()

    asset = query.data.replace("threshold_", "")

    uid = query.from_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    data, _ = get_asset_data(asset)

    await query.message.reply_text(
        T[lang]["threshold"].format(
            name=data["name"]
        ),
        parse_mode="HTML",
        reply_markup=threshold_kb(asset)
    )


async def cb_set_threshold(update, context):

    query = update.callback_query

    await query.answer()

    parts = query.data.split("_")

    asset = parts[1]
    threshold = float(parts[2])

    uid = query.from_user.id

    await set_threshold(
        uid,
        asset,
        threshold
    )

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    data, _ = get_asset_data(asset)

    await query.message.reply_text(
        T[lang]["threshold_saved"].format(
            name=data["name"],
            threshold=threshold
        ),
        parse_mode="HTML"
    )


# ============================================================
# MARKET
# ============================================================

async def show_market(update, context):

    uid = update.effective_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"
    asset_type = row[2] if row else "crypto"

    source = CRYPTO if asset_type == "crypto" else STOCKS

    symbols = list(source.keys())[:8]

    async def fetch(symbol):
        try:
            data = await get_market_data(symbol)
            return symbol, data
        except Exception:
            return symbol, None

    results = await asyncio.gather(
        *(fetch(symbol) for symbol in symbols)
    )

    text = T[lang]["market"]

    for symbol, market in results:

        if not market:
            continue

        info = source[symbol]

        direction = (
            "🟢"
            if market["change"] >= 0
            else "🔴"
        )

        text += (
            f"{direction} <b>{info['name']}</b>\n"
            f"${market['price']:,.2f} "
            f"({market['change']:+.2f}%)\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ============================================================
# SIGNAL HISTORY
# ============================================================

async def show_history(update, context):

    uid = update.effective_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    signals = await get_signals(uid)

    if not signals:
        await update.message.reply_text(
            T[lang]["history_empty"]
        )
        return

    text = T[lang]["history_title"]

    for asset, old, new, change, created in signals:

        data, _ = get_asset_data(asset)

        emoji = (
            "📈"
            if change > 0
            else "📉"
        )

        name = (
            data["name"]
            if data
            else asset
        )

        text += (
            f"{emoji} <b>{name}</b>\n"
            f"${old:,.2f} → ${new:,.2f}\n"
            f"Изменение: {change:+.2f}%\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ============================================================
# VIRTUAL PORTFOLIO
# ============================================================

async def show_portfolio(update, context):

    uid = update.effective_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    positions = await get_virtual_positions(uid)

    if not positions:

        await update.message.reply_text(
            T[lang]["portfolio_empty"],
            reply_markup=portfolio_kb()
        )

        return

    text = T[lang]["portfolio"]

    total_invested = 0
    total_value = 0

    for asset, invested, quantity, buy_price in positions:

        data, _ = get_asset_data(asset)

        try:
            market = await get_market_data(asset)
            current_price = market["price"]

            current_value = quantity * current_price

        except Exception:
            current_price = buy_price
            current_value = invested

        pnl = current_value - invested

        total_invested += invested
        total_value += current_value

        emoji = (
            "🟢"
            if pnl >= 0
            else "🔴"
        )

        text += (
            f"{data['emoji']} <b>{data['name']}</b>\n"
            f"Вложено: ${invested:,.2f}\n"
            f"Стоимость: ${current_value:,.2f}\n"
            f"{emoji} P/L: {pnl:+,.2f}$\n\n"
        )

    total_pnl = total_value - total_invested

    text += (
        "━━━━━━━━━━━━\n"
        f"💵 Всего вложено: ${total_invested:,.2f}\n"
        f"💰 Текущая стоимость: ${total_value:,.2f}\n"
        f"📊 Результат: {total_pnl:+,.2f}$\n\n"
        + T[lang]["virtual_only"]
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=portfolio_kb()
    )


async def virtual_add(update, context):

    query = update.callback_query

    await query.answer()

    uid = query.from_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    context.user_data["waiting_virtual"] = True

    await query.message.reply_text(
        T[lang]["portfolio_help"],
        parse_mode="HTML",
        reply_markup=back_kb(lang)
    )


async def process_virtual_position(
    update,
    context,
    text
):

    if not context.user_data.get("waiting_virtual"):
        return False

    parts = text.strip().split()

    if len(parts) != 2:
        return False

    asset_input = parts[0]

    try:
        amount = float(parts[1])

        if amount <= 0:
            return False

    except ValueError:
        return False

    found = find_asset(asset_input)

    if not found:
        return False

    _, asset, data = found

    uid = update.effective_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    try:
        market = await get_market_data(asset)

        price = market["price"]

        quantity = amount / price

        await add_virtual_position(
            uid,
            asset,
            amount,
            quantity,
            price
        )

        context.user_data["waiting_virtual"] = False

        await update.message.reply_text(
            T[lang]["position_added"].format(
                name=data["name"],
                amount=amount
            ),
            parse_mode="HTML"
        )

        return True

    except Exception:
        logger.exception("Virtual portfolio error")

        return False


# ============================================================
# CHART ANALYSIS
# ============================================================

async def show_chart(update, context):

    uid = update.effective_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    context.user_data["waiting_chart"] = True

    await update.message.reply_text(
        T[lang]["chart"],
        reply_markup=back_kb(lang)
    )


async def handle_photo(update, context):

    uid = update.effective_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    if not context.user_data.get("waiting_chart"):
        await update.message.reply_text(
            "Сначала выбери «🖼 Анализ графика»."
        )
        return

    context.user_data["waiting_chart"] = False

    await update.message.reply_text(
        T[lang]["analyzing"]
    )

    try:

        photo = update.message.photo[-1]

        telegram_file = await context.bot.get_file(
            photo.file_id
        )

        data = await telegram_file.download_as_bytearray()

        image_b64 = base64.b64encode(
            bytes(data)
        ).decode("utf-8")

        if lang == "ru":

            prompt = """
Проанализируй изображение графика.

Это образовательный анализ, а не торговая рекомендация.

Определи:

📈 Тренд
• восходящий
• нисходящий
• боковой

📊 Структура
• возможные уровни поддержки
• возможные уровни сопротивления
• заметные паттерны

⚠️ Риски

🔎 Что стоит наблюдать дальше

Если изображение недостаточно качественное,
честно скажи об этом.

Не утверждай, что цена обязательно пойдёт вверх или вниз.
Не говори просто "покупай" или "продавай".

Ответ должен быть понятным новичку.
"""

        else:

            prompt = """
Analyze the chart image.

This is educational analysis, not a trading recommendation.

Identify:

📈 Trend
• bullish
• bearish
• sideways

📊 Structure
• possible support
• possible resistance
• visible patterns

⚠️ Risks

🔎 What to watch next

If the image is unclear, say so.

Do not claim that price will definitely move up or down.
Do not simply say buy or sell.

Keep the explanation beginner-friendly.
"""

        result = await asyncio.to_thread(
            ai_image,
            prompt,
            image_b64
        )

        await update.message.reply_text(
            result
        )

    except Exception:

        logger.exception("Chart analysis failed")

        await update.message.reply_text(
            T[lang]["ai_error"]
        )


# ============================================================
# AI CHAT
# ============================================================

async def show_ai(update, context):

    uid = update.effective_user.id

    row = await get_user(uid)
    lang = row[1] if row else "ru"

    context.user_data["waiting_ai"] = True

    await update.message.reply_text(
        T[lang]["ai"],
        reply_markup=back_kb(lang)
    )


async def ai_chat(update, context, text):

    uid = update.effective_user.id

    row = await get_user(uid)

    lang = row[1] if row else "ru"

    try:

        watchlist = await get_watchlist(uid)

        context_info = ""

        if watchlist:

            assets = []

            for asset, _, _ in watchlist:
                data, _ = get_asset_data(asset)

                if data:
                    assets.append(data["name"])

            context_info = (
                "\nПользователь отслеживает: "
                + ", ".join(assets)
            )

        system_prompt = f"""
Ты — Vortex AI, помощник учебного приложения
по финансам, программированию и технологиям.

Язык пользователя: {lang}.
{context_info}

Отвечай понятно и кратко.

Если вопрос касается финансов:
- объясняй понятия;
- показывай возможные сценарии;
- объясняй риски;
- не выдавай неопределённые прогнозы как факты;
- не говори пользователю просто "покупай" или "продавай".

Ты не выполняешь реальные финансовые операции.

Если вопрос вообще не связан с финансами,
IT или технологиями, можешь ответить нормально,
если запрос безопасен.
"""

        prompt = (
            system_prompt
            + "\n\nВопрос пользователя:\n"
            + text
        )

        result = await asyncio.to_thread(
            ai_text,
            prompt
        )

        await update.message.reply_text(
            result
        )

    except Exception:

        logger.exception("AI chat error")

        await update.message.reply_text(
            T[lang]["ai_error"]
        )


# ============================================================
# TEXT HANDLER
# ============================================================

async def handle_text(update, context):

    text = update.message.text.strip()

    uid = update.effective_user.id

    await ensure_user(
        uid,
        update.effective_chat.id
    )

    row = await get_user(uid)

    lang = row[1] if row else "ru"

    # Back button
    if text in [
        T["ru"]["back"],
        T["en"]["back"]
    ]:

        context.user_data.clear()

        await update.message.reply_text(
            T[lang]["menu"],
            reply_markup=main_kb(lang)
        )

        return

    # Content filter
    if is_blocked(text):

        await update.message.reply_text(
            T[lang]["blocked"]
        )

        return

    # Virtual portfolio input
    if await process_virtual_position(
        update,
        context,
        text
    ):
        return

    # Main buttons

    if text == T[lang]["btn_track"]:

        await show_watchlist(
            update,
            context
        )

    elif text == T[lang]["btn_market"]:

        await show_market(
            update,
            context
        )

    elif text == T[lang]["btn_chart"]:

        await show_chart(
            update,
            context
        )

    elif text == T[lang]["btn_ai"]:

        await show_ai(
            update,
            context
        )

    elif text == T[lang]["btn_portfolio"]:

        await show_portfolio(
            update,
            context
        )

    elif text == T[lang]["btn_history"]:

        await show_history(
            update,
            context
        )

    elif text == T[lang]["btn_settings"]:

        keyboard = ReplyKeyboardMarkup(
            [
                [T[lang]["set_lang"]],
                [T[lang]["set_type"]],
                [T[lang]["back"]],
            ],
            resize_keyboard=True
        )

        await update.message.reply_text(
            T[lang]["settings"],
            reply_markup=keyboard
        )

    elif text == T[lang]["set_lang"]:

        await update.message.reply_text(
            T[lang]["choose_lang"],
            reply_markup=lang_kb()
        )

    elif text == T[lang]["set_type"]:

        await update.message.reply_text(
            T[lang]["choose_type"],
            reply_markup=type_kb()
        )

    else:

        found = find_asset(text)

        if found:

            _, asset, data = found

            try:

                market = await get_market_data(asset)

                await update.message.reply_text(
                    T[lang]["asset_card"].format(
                        emoji=data["emoji"],
                        name=data["name"],
                        ticker=asset,
                        price=market["price"],
                        change=market["change"],
                        threshold=DEFAULT_THRESHOLD
                    ),
                    parse_mode="HTML"
                )

                analysis = await asyncio.to_thread(
                    ai_asset_analysis,
                    data["name"],
                    asset,
                    market["price"],
                    market["change"],
                    lang
                )

                await update.message.reply_text(
                    analysis
                )

            except Exception:

                logger.exception(
                    "Asset text analysis error"
                )

                await update.message.reply_text(
                    T[lang]["server_error"]
                )

        else:

            await ai_chat(
                update,
                context,
                text
            )


# ============================================================
# PRICE MONITOR
# ============================================================

async def price_check(context):

    items = await get_all_watchlist()

    for uid, asset, threshold, last_price in items:

        try:

            market = await get_market_data(asset)

            current_price = market["price"]

            if last_price is None:

                await update_last_price(
                    uid,
                    asset,
                    current_price
                )

                continue

            change = (
                (current_price - last_price)
                / last_price
                * 100
            )

            if abs(change) >= threshold:

                row = await get_user(uid)

                if not row:
                    continue

                lang = row[1]
                chat_id = row[3]

                data, _ = get_asset_data(asset)

                direction = (
                    "📈"
                    if change > 0
                    else "📉"
                )

                message = (
                    f"🚨 <b>{data['name']}</b>\n\n"
                    f"{direction} Изменение: "
                    f"<b>{change:+.2f}%</b>\n"
                    f"Было: ${last_price:,.2f}\n"
                    f"Сейчас: ${current_price:,.2f}"
                )

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML"
                )

                await add_signal(
                    uid,
                    asset,
                    last_price,
                    current_price,
                    change
                )

                await update_last_price(
                    uid,
                    asset,
                    current_price
                )

        except Exception:

            logger.exception(
                "Price check failed for %s",
                asset
            )


# ============================================================
# CALLBACK ROUTER
# ============================================================

async def unknown_callback(update, context):

    query = update.callback_query

    await query.answer(
        "Эта кнопка больше не актуальна."
    )


# ============================================================
# MAIN
# ============================================================

async def post_init(application):

    await init_db()

    logger.info(
        "Database initialized"
    )


def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # Language

    app.add_handler(
        CallbackQueryHandler(
            cb_lang,
            pattern=r"^lang_(ru|en)$"
        )
    )

    # Asset type

    app.add_handler(
        CallbackQueryHandler(
            cb_type,
            pattern=r"^type_(crypto|stocks)$"
        )
    )

    # Watchlist

    app.add_handler(
        CallbackQueryHandler(
            choose_asset,
            pattern=r"^choose_asset$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            cb_add_asset,
            pattern=r"^add_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            cb_remove_asset,
            pattern=r"^remove_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            cb_view_asset,
            pattern=r"^view_"
        )
    )

    # Threshold

    app.add_handler(
        CallbackQueryHandler(
            cb_threshold,
            pattern=r"^threshold_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            cb_set_threshold,
            pattern=r"^thr_"
        )
    )

    # Virtual portfolio

    app.add_handler(
        CallbackQueryHandler(
            virtual_add,
            pattern=r"^virtual_add$"
        )
    )

    # Images

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    # Text

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    # Price monitoring

    app.job_queue.run_repeating(
        price_check,
        interval=PRICE_CHECK_INTERVAL,
        first=10
    )

    logger.info(
        "🌪️ Vortex 2.0 started"
    )

    app.run_polling()


if __name__ == "__main__":
    main()