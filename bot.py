import os
import asyncio
import logging
import base64
import html

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

DB_NAME = "vortex.db"
THRESHOLD = 2.0
AI_MODEL = "gpt-4o-mini"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not configured")

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# ============================================================
# TRANSLATIONS
# ============================================================

T = {
    "ru": {
        "welcome": (
            "👋 Добро пожаловать в Vortex!\n\n"
            "Я твой помощник по рынку.\n"
            "Здесь можно отслеживать криптовалюты и акции, "
            "смотреть рынок, открывать графики TradingView "
            "и получать учебный AI-анализ."
        ),

        "choose_lang": "🌍 Выберите язык:",

        "menu": "🏠 Главное меню:",

        "track": "📈 Выберите актив для отслеживания:",

        "track_ok": (
            "✅ Отслеживание включено\n\n"
            "💎 {name}\n"
            "💰 Цена: <b>${price:,.2f}</b>\n"
            "📊 Изменение: <b>{change:+.2f}%</b>\n\n"
            "🔔 Уведомлю, если цена изменится более чем на {thr}%."
        ),

        "market": "📊 <b>Рыночный обзор</b>\n\n",

        "chart": (
            "🖼 Пришлите скриншот графика.\n\n"
            "AI попробует определить тренд, уровни и возможные сценарии."
        ),

        "ai": (
            "💬 Напишите вопрос.\n\n"
            "Я могу объяснить понятия из IT, финансов, "
            "криптовалют, акций и других тем."
        ),

        "ai_err": (
            "😕 AI временно не отвечает.\n"
            "Попробуйте ещё раз немного позже."
        ),

        "nsfw": (
            "Извините, я не могу выполнить этот запрос. "
            "Давайте поговорим о криптовалютах, акциях или IT. 😊"
        ),

        "settings": "⚙️ Настройки",

        "set_lang": "🌍 Сменить язык",

        "set_type": "📊 Сменить тип актива",

        "back": "◀️ Назад",

        "btn_track": "📈 Отслеживать актив",

        "btn_market": "📊 Рыночный обзор",

        "btn_tradingview": "📊 TradingView",

        "btn_chart": "🖼 Анализ графика",

        "btn_ai": "💬 AI Помощник",

        "btn_settings": "⚙️ Настройки",

        "type_crypto": "💎 Криптовалюты",

        "type_stocks": "📈 Акции",

        "choose_type": "Выберите тип актива:",

        "choose_tradingview": (
            "📊 <b>TradingView</b>\n\n"
            "Выберите криптовалюту или акцию:"
        ),

        "tradingview_asset": (
            "📊 <b>{name}</b>\n\n"
            "💰 Цена: <b>${price:,.2f}</b>\n"
            "📈 Изменение: <b>{change:+.2f}%</b>\n\n"
            "Выберите действие:"
        ),

        "open_tradingview": "📊 Открыть TradingView",

        "ai_analysis": "🤖 AI-анализ",

        "analysis_loading": "🤖 Анализирую рыночные данные...",

        "analysis_title": "🤖 <b>AI-анализ {name}</b>",

        "analysis_warning": (
            "\n\n⚠️ <b>Важно:</b> AI-анализ может ошибаться "
            "и не является финансовой рекомендацией."
        ),

        "analyzing": "🔍 Анализирую график...",

        "lang_changed": "🇷🇺 Язык изменён!",

        "type_changed": "📊 Тип актива изменён!",

        "unknown": (
            "Я не совсем понял запрос.\n\n"
            "Используйте меню или напишите название "
            "криптовалюты/акции, например BTC или AAPL."
        ),

        "err": "❌ Ошибка сервера. Попробуйте позже.",

        "asset_info": (
            "💎 <b>{name}</b> ({ticker})\n\n"
            "💰 Цена: <b>${price:,.2f}</b>\n"
            "📊 Изменение: <b>{change:+.2f}%</b>\n\n"
            "⏳ Готовлю учебный анализ..."
        ),
    },

    "en": {
        "welcome": (
            "👋 Welcome to Vortex!\n\n"
            "Your market assistant.\n"
            "Track crypto and stocks, view the market, "
            "open TradingView charts and get educational AI analysis."
        ),

        "choose_lang": "🌍 Choose language:",

        "menu": "🏠 Main menu:",

        "track": "📈 Choose an asset to track:",

        "track_ok": (
            "✅ Tracking enabled\n\n"
            "💎 {name}\n"
            "💰 Price: <b>${price:,.2f}</b>\n"
            "📊 Change: <b>{change:+.2f}%</b>\n\n"
            "🔔 I will alert you if the price changes by more than {thr}%."
        ),

        "market": "📊 <b>Market Overview</b>\n\n",

        "chart": (
            "🖼 Send a chart screenshot.\n\n"
            "AI will try to identify the trend, levels and possible scenarios."
        ),

        "ai": (
            "💬 Send me a question.\n\n"
            "I can explain topics related to IT, finance, "
            "crypto, stocks and more."
        ),

        "ai_err": (
            "😕 AI is temporarily unavailable.\n"
            "Please try again later."
        ),

        "nsfw": (
            "Sorry, I cannot fulfill this request. "
            "Let's talk about crypto, stocks or IT. 😊"
        ),

        "settings": "⚙️ Settings",

        "set_lang": "🌍 Change language",

        "set_type": "📊 Change asset type",

        "back": "◀️ Back",

        "btn_track": "📈 Track asset",

        "btn_market": "📊 Market overview",

        "btn_tradingview": "📊 TradingView",

        "btn_chart": "🖼 Chart analysis",

        "btn_ai": "💬 AI Assistant",

        "btn_settings": "⚙️ Settings",

        "type_crypto": "💎 Crypto",

        "type_stocks": "📈 Stocks",

        "choose_type": "Choose asset type:",

        "choose_tradingview": (
            "📊 <b>TradingView</b>\n\n"
            "Choose a cryptocurrency or stock:"
        ),

        "tradingview_asset": (
            "📊 <b>{name}</b>\n\n"
            "💰 Price: <b>${price:,.2f}</b>\n"
            "📈 Change: <b>{change:+.2f}%</b>\n\n"
            "Choose an action:"
        ),

        "open_tradingview": "📊 Open TradingView",

        "ai_analysis": "🤖 AI Analysis",

        "analysis_loading": "🤖 Analyzing market data...",

        "analysis_title": "🤖 <b>AI analysis: {name}</b>",

        "analysis_warning": (
            "\n\n⚠️ <b>Important:</b> AI analysis can be wrong "
            "and is not financial advice."
        ),

        "analyzing": "🔍 Analyzing chart...",

        "lang_changed": "🇺🇸 Language changed!",

        "type_changed": "📊 Asset type changed!",

        "unknown": (
            "I didn't understand.\n\n"
            "Use the menu or type an asset name, "
            "for example BTC or AAPL."
        ),

        "err": "❌ Server error. Please try again later.",

        "asset_info": (
            "💎 <b>{name}</b> ({ticker})\n\n"
            "💰 Price: <b>${price:,.2f}</b>\n"
            "📊 Change: <b>{change:+.2f}%</b>\n\n"
            "⏳ Preparing educational analysis..."
        ),
    },
}


# ============================================================
# ASSETS
# ============================================================

CRYPTO = {
    "BTCUSDT": {
        "name": "Bitcoin",
        "aliases": ["bitcoin", "btc", "биткоин", "биток"],
    },
    "ETHUSDT": {
        "name": "Ethereum",
        "aliases": ["ethereum", "eth", "эфириум", "эфир"],
    },
    "BNBUSDT": {
        "name": "BNB",
        "aliases": ["bnb", "бнб", "binance coin"],
    },
    "SOLUSDT": {
        "name": "Solana",
        "aliases": ["solana", "sol", "солана"],
    },
    "XRPUSDT": {
        "name": "XRP",
        "aliases": ["xrp", "рипл", "ripple"],
    },
    "ADAUSDT": {
        "name": "Cardano",
        "aliases": ["cardano", "ada", "кардано"],
    },
    "DOGEUSDT": {
        "name": "Dogecoin",
        "aliases": ["dogecoin", "doge", "доге", "догикоин"],
    },
    "DOTUSDT": {
        "name": "Polkadot",
        "aliases": ["polkadot", "dot", "полкадот"],
    },
    "AVAXUSDT": {
        "name": "Avalanche",
        "aliases": ["avalanche", "avax", "аваланч"],
    },
    "LINKUSDT": {
        "name": "Chainlink",
        "aliases": ["chainlink", "link", "чейнлинк", "линк"],
    },
    "LTCUSDT": {
        "name": "Litecoin",
        "aliases": ["litecoin", "ltc", "лайткоин"],
    },
    "UNIUSDT": {
        "name": "Uniswap",
        "aliases": ["uniswap", "uni", "юнисвап"],
    },
    "ATOMUSDT": {
        "name": "Cosmos",
        "aliases": ["cosmos", "atom", "космос"],
    },
    "ETCUSDT": {
        "name": "Ethereum Classic",
        "aliases": ["ethereum classic", "etc", "эфириум классик"],
    },
    "MATICUSDT": {
        "name": "Polygon",
        "aliases": ["polygon", "matic", "полигон", "матик"],
    },
}


STOCKS = {
    "AAPL": {
        "name": "Apple",
        "aliases": ["apple", "aapl", "эпл", "аппл"],
    },
    "TSLA": {
        "name": "Tesla",
        "aliases": ["tesla", "tsla", "тесла"],
    },
    "GOOGL": {
        "name": "Alphabet",
        "aliases": ["google", "googl", "гугл"],
    },
    "AMZN": {
        "name": "Amazon",
        "aliases": ["amazon", "amzn", "амазон"],
    },
    "MSFT": {
        "name": "Microsoft",
        "aliases": ["microsoft", "msft", "майкрософт"],
    },
    "NVDA": {
        "name": "NVIDIA",
        "aliases": ["nvidia", "nvda", "нвидиа"],
    },
    "META": {
        "name": "Meta",
        "aliases": ["meta", "мета", "facebook", "фейсбук"],
    },
    "NFLX": {
        "name": "Netflix",
        "aliases": ["netflix", "nflx", "нетфликс"],
    },
    "AMD": {
        "name": "AMD",
        "aliases": ["amd", "эйэмди"],
    },
    "BABA": {
        "name": "Alibaba",
        "aliases": ["alibaba", "baba", "алибаба"],
    },
}


# ============================================================
# BLOCKED CONTENT
# ============================================================

BLOCKED = [
    "голый",
    "голые",
    "голая",
    "раздень",
    "раздеть",
    "раздевай",
    "порно",
    "порнуха",
    "xxx",
    "ххх",
    "нюдс",
    "нюдсы",
    "nude",
    "naked",
    "nsfw",
    "sex",
    "секс",
    "эротика",
    "hentai",
    "хентай",
    "детское",
    "child",
    "убей",
    "убий",
    "насилие",
    "террор",
]


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
                asset TEXT,
                price REAL,
                chat_id INTEGER
            )
        """)

        await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT lang, type, asset, price, chat_id
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        return await cursor.fetchone()


async def set_lang(user_id, lang):
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            INSERT INTO users (user_id, lang)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET lang=?
            """,
            (user_id, lang, lang)
        )

        await db.commit()


async def set_type(user_id, asset_type):
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            INSERT INTO users (user_id, type)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET type=?
            """,
            (user_id, asset_type, asset_type)
        )

        await db.commit()


async def set_asset(user_id, asset, chat_id):
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            INSERT INTO users
            (user_id, asset, chat_id)
            VALUES (?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                asset=?,
                chat_id=?,
                price=NULL
            """,
            (
                user_id,
                asset,
                chat_id,
                asset,
                chat_id,
            )
        )

        await db.commit()


async def update_price(user_id, price):
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE users
            SET price=?
            WHERE user_id=?
            """,
            (price, user_id)
        )

        await db.commit()


async def get_tracking():
    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT user_id, asset, price, chat_id
            FROM users
            WHERE asset IS NOT NULL
            """
        )

        return await cursor.fetchall()


# ============================================================
# MARKET API
# ============================================================

async def get_crypto(symbol):
    url = "https://api.binance.com/api/v3/ticker/24hr"

    async with aiohttp.ClientSession() as session:

        async with session.get(
            url,
            params={"symbol": symbol},
            timeout=15
        ) as response:

            response.raise_for_status()

            data = await response.json()

            return {
                "price": float(data["lastPrice"]),
                "change": float(data["priceChangePercent"]),
                "high": float(data["highPrice"]),
                "low": float(data["lowPrice"]),
                "volume": float(data["volume"]),
            }


async def get_stock(ticker):
    url = (
        f"https://query1.finance.yahoo.com/"
        f"v8/finance/chart/{ticker}"
    )

    async with aiohttp.ClientSession() as session:

        async with session.get(
            url,
            params={
                "interval": "1d",
                "range": "5d",
            },
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=15
        ) as response:

            response.raise_for_status()

            data = await response.json()

            result = data["chart"]["result"][0]

            meta = result["meta"]

            price = meta.get("regularMarketPrice")

            previous = (
                meta.get("previousClose")
                or meta.get("chartPreviousClose")
                or price
            )

            change = 0

            if previous:
                change = (
                    (price - previous)
                    / previous
                    * 100
                )

            return {
                "price": float(price),
                "change": float(change),
                "high": float(
                    meta.get("regularMarketDayHigh")
                    or price
                ),
                "low": float(
                    meta.get("regularMarketDayLow")
                    or price
                ),
                "volume": float(
                    meta.get("regularMarketVolume")
                    or 0
                ),
            }


async def get_market_data(asset):
    if asset in CRYPTO:
        return await get_crypto(asset)

    if asset in STOCKS:
        return await get_stock(asset)

    raise ValueError("Unknown asset")


# ============================================================
# OPENAI
# ============================================================

def ai_ask(prompt):
    response = client.responses.create(
        model=AI_MODEL,
        instructions=(
            "You are Vortex AI, an educational assistant. "
            "Explain things clearly and briefly. "
            "Never claim that a financial market prediction "
            "is guaranteed. Do not present predictions as certainty."
        ),
        input=prompt,
    )

    return response.output_text


def ai_analyze_image(image_b64, prompt):
    response = client.responses.create(
        model=AI_MODEL,
        instructions=(
            "You are Vortex AI analyzing a financial chart "
            "for educational purposes. "
            "Do not guarantee future price movements. "
            "Do not give certainty about buying or selling."
        ),
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


# ============================================================
# KEYBOARDS
# ============================================================

def main_kb(lang):
    return ReplyKeyboardMarkup(
        [
            [T[lang]["btn_track"]],
            [T[lang]["btn_market"]],
            [T[lang]["btn_tradingview"]],
            [T[lang]["btn_chart"]],
            [T[lang]["btn_ai"]],
            [T[lang]["btn_settings"]],
        ],
        resize_keyboard=True,
    )


def back_kb(lang):
    return ReplyKeyboardMarkup(
        [
            [T[lang]["back"]]
        ],
        resize_keyboard=True,
    )


def type_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💎 Крипта / Crypto",
                    callback_data="type_crypto",
                ),
                InlineKeyboardButton(
                    "📈 Акции / Stocks",
                    callback_data="type_stocks",
                ),
            ]
        ]
    )


def lang_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="lang_ru",
                ),
                InlineKeyboardButton(
                    "🇺🇸 English",
                    callback_data="lang_en",
                ),
            ]
        ]
    )


def crypto_kb():
    buttons = []
    row = []

    for index, (symbol, data) in enumerate(
        CRYPTO.items(),
        start=1
    ):

        row.append(
            InlineKeyboardButton(
                data["name"],
                callback_data=f"track_{symbol}",
            )
        )

        if index % 2 == 0:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)


def stocks_kb():
    buttons = []
    row = []

    for index, (ticker, data) in enumerate(
        STOCKS.items(),
        start=1
    ):

        row.append(
            InlineKeyboardButton(
                data["name"],
                callback_data=f"track_{ticker}",
            )
        )

        if index % 2 == 0:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)


def tradingview_kb():
    buttons = []
    row = []

    for symbol, data in CRYPTO.items():

        row.append(
            InlineKeyboardButton(
                f"💎 {data['name']}",
                callback_data=f"tv_{symbol}",
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    for ticker, data in STOCKS.items():

        row.append(
            InlineKeyboardButton(
                f"📈 {data['name']}",
                callback_data=f"tv_{ticker}",
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)


# ============================================================
# ASSET SEARCH
# ============================================================

def find_asset(text):
    text = text.lower().strip()

    for symbol, data in CRYPTO.items():

        if (
            text in data["aliases"]
            or text == symbol.lower().replace("usdt", "")
        ):
            return (
                "crypto",
                symbol,
                data,
            )

    for ticker, data in STOCKS.items():

        if (
            text in data["aliases"]
            or text == ticker.lower()
        ):
            return (
                "stock",
                ticker,
                data,
            )

    return None


def is_blocked(text):
    text_lower = text.lower()

    return any(
        word in text_lower
        for word in BLOCKED
    )


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    if row is None or row[0] is None:

        await update.message.reply_text(
            T["ru"]["choose_lang"],
            reply_markup=lang_kb(),
        )

        return

    lang = row[0]

    await update.message.reply_text(
        T[lang]["welcome"],
        reply_markup=main_kb(lang),
    )


# ============================================================
# LANGUAGE CALLBACK
# ============================================================

async def cb_lang(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    lang = query.data.replace(
        "lang_",
        "",
    )

    user_id = query.from_user.id

    await set_lang(
        user_id,
        lang,
    )

    try:
        await query.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        query.message.chat.id,
        T[lang]["welcome"],
        reply_markup=main_kb(lang),
    )


# ============================================================
# TYPE CALLBACK
# ============================================================

async def cb_type(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    asset_type = query.data.replace(
        "type_",
        "",
    )

    user_id = query.from_user.id

    await set_type(
        user_id,
        asset_type,
    )

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    await query.message.reply_text(
        T[lang]["type_changed"]
    )


# ============================================================
# TRACK ASSET
# ============================================================

async def show_track(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    asset_type = (
        row[1]
        if row and row[1]
        else "crypto"
    )

    if asset_type == "crypto":

        await update.message.reply_text(
            T[lang]["track"],
            reply_markup=crypto_kb(),
        )

    else:

        await update.message.reply_text(
            T[lang]["track"],
            reply_markup=stocks_kb(),
        )


async def cb_track(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    asset = query.data.replace(
        "track_",
        "",
    )

    user_id = query.from_user.id

    chat_id = query.message.chat.id

    await set_asset(
        user_id,
        asset,
        chat_id,
    )

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    try:

        data = await get_market_data(asset)

        if asset in CRYPTO:
            name = CRYPTO[asset]["name"]
        else:
            name = STOCKS[asset]["name"]

        await update_price(
            user_id,
            data["price"],
        )

        await query.message.reply_text(
            T[lang]["track_ok"].format(
                name=name,
                price=data["price"],
                change=data["change"],
                thr=THRESHOLD,
            ),
            parse_mode="HTML",
        )

    except Exception:

        logging.exception(
            "Tracking error"
        )

        await query.message.reply_text(
            T[lang]["err"]
        )


# ============================================================
# MARKET OVERVIEW
# ============================================================

async def show_market(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    asset_type = (
        row[1]
        if row and row[1]
        else "crypto"
    )

    text = T[lang]["market"]

    try:

        if asset_type == "crypto":

            assets = list(
                CRYPTO.items()
            )[:5]

            for symbol, data in assets:

                market = await get_crypto(
                    symbol
                )

                text += (
                    f"💎 <b>{html.escape(data['name'])}</b>\n"
                    f"${market['price']:,.2f} "
                    f"({market['change']:+.2f}%)\n\n"
                )

        else:

            assets = list(
                STOCKS.items()
            )[:5]

            for ticker, data in assets:

                market = await get_stock(
                    ticker
                )

                text += (
                    f"📈 <b>{html.escape(data['name'])}</b>\n"
                    f"${market['price']:,.2f} "
                    f"({market['change']:+.2f}%)\n\n"
                )

        await update.message.reply_text(
            text,
            parse_mode="HTML",
        )

    except Exception:

        logging.exception(
            "Market overview error"
        )

        await update.message.reply_text(
            T[lang]["err"]
        )


# ============================================================
# TRADINGVIEW
# ============================================================

async def show_tradingview(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    await update.message.reply_text(
        T[lang]["choose_tradingview"],
        reply_markup=tradingview_kb(),
        parse_mode="HTML",
    )


def tradingview_symbol(asset):

    if asset in CRYPTO:

        return (
            "BINANCE:"
            + asset
        )

    if asset in STOCKS:

        return (
            "NASDAQ:"
            + asset
        )

    return asset


async def cb_tradingview(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    asset = query.data.replace(
        "tv_",
        "",
    )

    user_id = query.from_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    try:

        market = await get_market_data(
            asset
        )

        if asset in CRYPTO:

            name = CRYPTO[asset]["name"]

        else:

            name = STOCKS[asset]["name"]

        tv_symbol = tradingview_symbol(
            asset
        )

        chart_url = (
            "https://www.tradingview.com/chart/"
            f"?symbol={tv_symbol}"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        T[lang]["open_tradingview"],
                        url=chart_url,
                    )
                ],
                [
                    InlineKeyboardButton(
                        T[lang]["ai_analysis"],
                        callback_data=(
                            f"tvanalyze_{asset}"
                        ),
                    )
                ],
            ]
        )

        await query.message.reply_text(
            T[lang]["tradingview_asset"].format(
                name=html.escape(name),
                price=market["price"],
                change=market["change"],
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception:

        logging.exception(
            "TradingView error"
        )

        await query.message.reply_text(
            T[lang]["err"]
        )


# ============================================================
# AI MARKET ANALYSIS
# ============================================================

async def cb_tv_analyze(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    asset = query.data.replace(
        "tvanalyze_",
        "",
    )

    user_id = query.from_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    await query.message.reply_text(
        T[lang]["analysis_loading"]
    )

    try:

        market = await get_market_data(
            asset
        )

        if asset in CRYPTO:

            data = CRYPTO[asset]

            category = "криптовалюта"

        else:

            data = STOCKS[asset]

            category = "акция"

        prompt = f"""
Ты — Vortex AI.

Проведи краткий образовательный анализ
рыночного актива.

Актив:
{data['name']}

Тикер:
{asset}

Тип:
{category}

Текущая цена:
${market['price']:,.2f}

Изменение:
{market['change']:+.2f}%

Дневной максимум:
${market['high']:,.2f}

Дневной минимум:
${market['low']:,.2f}

Объём:
{market['volume']:,.2f}

Сделай анализ в следующем формате:

📊 Тренд:
Кратко опиши текущую ситуацию.

🟢 Позитивные факторы:
2-3 пункта.

🔴 Риски:
2-3 пункта.

🧠 Сценарий:
Выбери один:
- Бычий
- Нейтральный
- Медвежий

📚 Что стоит наблюдать:
2-3 показателя или события.

Не утверждай, что актив гарантированно вырастет
или упадёт.

Не обещай прибыль.

Не выдавай результат как персональную
финансовую рекомендацию.

Это образовательный анализ текущих данных.
"""

        result = await asyncio.to_thread(
            ai_ask,
            prompt,
        )

        await query.message.reply_text(
            T[lang]["analysis_title"].format(
                name=html.escape(
                    data["name"]
                )
            )
            + "\n\n"
            + result
            + T[lang]["analysis_warning"],
            parse_mode="HTML",
        )

    except Exception:

        logging.exception(
            "AI market analysis error"
        )

        await query.message.reply_text(
            T[lang]["ai_err"]
        )


# ============================================================
# CHART IMAGE ANALYSIS
# ============================================================

async def show_chart(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    await update.message.reply_text(
        T[lang]["chart"],
        reply_markup=back_kb(lang),
    )


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    await update.message.reply_text(
        T[lang]["analyzing"]
    )

    try:

        photo = update.message.photo[-1]

        telegram_file = (
            await context.bot.get_file(
                photo.file_id
            )
        )

        data = await telegram_file.download_as_bytearray()

        image_b64 = base64.b64encode(
            bytes(data)
        ).decode("utf-8")

        prompt = """
Ты анализируешь скриншот финансового графика
для образовательного приложения Vortex.

Определи, если это возможно:

1. 📊 Общий тренд.
2. 📈 Направление движения цены.
3. 🟢 Возможные признаки силы.
4. 🔴 Возможные признаки слабости.
5. 📍 Возможные уровни поддержки.
6. 📍 Возможные уровни сопротивления.
7. 📚 Что стоит наблюдать дальше.

Если на изображении недостаточно информации,
прямо скажи об этом.

В конце укажи:

🧠 Сценарий:
Бычий / Нейтральный / Медвежий

Не утверждай, что цена гарантированно
вырастет или упадёт.

Не давай гарантированных сигналов покупки
или продажи.

⚠️ AI-анализ может ошибаться.
"""

        result = await asyncio.to_thread(
            ai_analyze_image,
            image_b64,
            prompt,
        )

        await update.message.reply_text(
            result
            + T[lang]["analysis_warning"],
            parse_mode="HTML",
        )

    except Exception:

        logging.exception(
            "Image analysis error"
        )

        await update.message.reply_text(
            T[lang]["ai_err"]
        )


# ============================================================
# AI CHAT
# ============================================================

async def show_ai(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    await update.message.reply_text(
        T[lang]["ai"],
        reply_markup=back_kb(lang),
    )


async def ai_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    try:

        result = await asyncio.to_thread(
            ai_ask,
            text,
        )

        await update.message.reply_text(
            result
        )

    except Exception:

        logging.exception(
            "AI chat error"
        )

        await update.message.reply_text(
            T[lang]["ai_err"]
        )


# ============================================================
# ASSET BY TEXT
# ============================================================

async def asset_by_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    asset_data = find_asset(text)

    if not asset_data:
        return False

    asset_type, symbol, data = asset_data

    try:

        market = await get_market_data(
            symbol
        )

        await update.message.reply_text(
            T[lang]["asset_info"].format(
                name=data["name"],
                ticker=symbol,
                price=market["price"],
                change=market["change"],
            ),
            parse_mode="HTML",
        )

        category = (
            "криптовалюта"
            if asset_type == "crypto"
            else "акция"
        )

        prompt = f"""
Ты — Vortex AI.

Пользователь запросил информацию
об активе.

Название:
{data['name']}

Тикер:
{symbol}

Тип:
{category}

Цена:
${market['price']:,.2f}

Изменение:
{market['change']:+.2f}%

Дневной максимум:
${market['high']:,.2f}

Дневной минимум:
${market['low']:,.2f}

Сделай короткий образовательный обзор:

1. Что это за актив.
2. Что сейчас происходит с ценой.
3. Какие факторы могут быть важны.
4. Основные риски.
5. Бычий / нейтральный / медвежий сценарий.

Не обещай прибыль.
Не говори, что нужно гарантированно покупать
или продавать актив.

⚠️ AI-анализ может ошибаться и не является
финансовой рекомендацией.
"""

        result = await asyncio.to_thread(
            ai_ask,
            prompt,
        )

        await update.message.reply_text(
            result
        )

    except Exception:

        logging.exception(
            "Asset analysis error"
        )

        await update.message.reply_text(
            T[lang]["err"]
        )

    return True


# ============================================================
# SETTINGS
# ============================================================

async def show_settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    keyboard = ReplyKeyboardMarkup(
        [
            [T[lang]["set_lang"]],
            [T[lang]["set_type"]],
            [T[lang]["back"]],
        ],
        resize_keyboard=True,
    )

    await update.message.reply_text(
        T[lang]["settings"],
        reply_markup=keyboard,
    )


# ============================================================
# TEXT HANDLER
# ============================================================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    text = update.message.text.strip()

    user_id = update.effective_user.id

    row = await get_user(user_id)

    lang = row[0] if row else "ru"

    # --------------------------------------------------------
    # BLOCKED CONTENT
    # --------------------------------------------------------

    if is_blocked(text):

        await update.message.reply_text(
            T[lang]["nsfw"]
        )

        return

    # --------------------------------------------------------
    # BACK
    # --------------------------------------------------------

    if text in [
        T["ru"]["back"],
        T["en"]["back"],
    ]:

        await update.message.reply_text(
            T[lang]["menu"],
            reply_markup=main_kb(lang),
        )

        return

    # --------------------------------------------------------
    # MENU
    # --------------------------------------------------------

    if text == T[lang]["btn_track"]:

        await show_track(
            update,
            context,
        )

    elif text == T[lang]["btn_market"]:

        await show_market(
            update,
            context,
        )

    elif text == T[lang]["btn_tradingview"]:

        await show_tradingview(
            update,
            context,
        )

    elif text == T[lang]["btn_chart"]:

        await show_chart(
            update,
            context,
        )

    elif text == T[lang]["btn_ai"]:

        await show_ai(
            update,
            context,
        )

    elif text == T[lang]["btn_settings"]:

        await show_settings(
            update,
            context,
        )

    elif text == T[lang]["set_lang"]:

        await update.message.reply_text(
            T[lang]["choose_lang"],
            reply_markup=lang_kb(),
        )

    elif text == T[lang]["set_type"]:

        await update.message.reply_text(
            T[lang]["choose_type"],
            reply_markup=type_kb(),
        )

    else:

        # Сначала ищем актив
        found = await asset_by_text(
            update,
            context,
            text,
        )

        # Если это не актив — отправляем AI
        if not found:

            await ai_chat(
                update,
                context,
                text,
            )


# ============================================================
# PRICE MONITOR
# ============================================================

async def price_check(
    context: ContextTypes.DEFAULT_TYPE
):
    users = await get_tracking()

    for (
        user_id,
        asset,
        last_price,
        chat_id,
    ) in users:

        if not asset or not chat_id:
            continue

        try:

            market = await get_market_data(
                asset
            )

            current_price = market["price"]

            if last_price is None:

                await update_price(
                    user_id,
                    current_price,
                )

                continue

            if last_price == 0:
                continue

            percentage = abs(
                (
                    current_price
                    - last_price
                )
                / last_price
                * 100
            )

            if percentage >= THRESHOLD:

                row = await get_user(
                    user_id
                )

                lang = (
                    row[0]
                    if row
                    else "ru"
                )

                if asset in CRYPTO:

                    name = CRYPTO[
                        asset
                    ]["name"]

                else:

                    name = STOCKS[
                        asset
                    ]["name"]

                direction = (
                    "📈"
                    if current_price > last_price
                    else "📉"
                )

                message = (
                    f"🚨 <b>{html.escape(name)}</b>\n\n"
                    f"{direction} "
                    f"Изменение: "
                    f"<b>{percentage:.2f}%</b>\n\n"
                    f"Было: "
                    f"<b>${last_price:,.2f}</b>\n"
                    f"Сейчас: "
                    f"<b>${current_price:,.2f}</b>"
                )

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML",
                )

                await update_price(
                    user_id,
                    current_price,
                )

        except Exception:

            logging.exception(
                f"Price check failed: {asset}"
            )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    logging.exception(
        "Unhandled exception:",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

async def post_init(
    application: Application
):
    await init_db()

    logging.info(
        "Database initialized"
    )


def main():

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            cb_lang,
            pattern=r"^lang_",
        )
    )

    # --------------------------------------------------------
    # TYPE
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            cb_type,
            pattern=r"^type_",
        )
    )

    # --------------------------------------------------------
    # TRACKING
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            cb_track,
            pattern=r"^track_",
        )
    )

    # --------------------------------------------------------
    # TRADINGVIEW
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            cb_tv_analyze,
            pattern=r"^tvanalyze_",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            cb_tradingview,
            pattern=r"^tv_",
        )
    )

    # --------------------------------------------------------
    # PHOTOS
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo,
        )
    )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_text,
        )
    )

    # --------------------------------------------------------
    # PRICE MONITOR
    # --------------------------------------------------------

    application.job_queue.run_repeating(
        price_check,
        interval=300,
        first=10,
    )

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    logging.info(
        "🌪️ Vortex started!"
    )

    application.run_polling()


if __name__ == "__main__":
    main()