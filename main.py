import os
import asyncio
import logging
import base64
import aiosqlite
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CRYPTO_SYMBOLS = {
    "Bitcoin": "BTCUSDT",
    "Ethereum": "ETHUSDT",
    "Binance Coin": "BNBUSDT",
    "Solana": "SOLUSDT"
}
CHECK_INTERVAL_MINUTES = 5
PRICE_CHANGE_THRESHOLD = 2.0

TEXTS = {
    'ru': {
        'choose_lang': 'Vyberite yazyk:',
        'welcome': 'Privet! Ya Vortex. Tvoy umnyy pomoshchnik v mire kriptovalyut.',
        'track_choose': 'Vyberi kriptovalyutu:',
        'tracking': 'Otslezhivayu {asset}\nTsena: ${price:,.2f}\n24ch: {change:+.2f}%',
        'market_loading': 'Sobirayu dannye s rynka...',
        'ask_chart': 'Prishli skrinshot grafika',
        'analyzing': 'Smotryu na grafik...',
        'ask_ai': 'Napishi vopros - ya otvechu!',
        'thinking': 'Dumayu...',
        'price_alert': 'Tsena izmenilas!\n{asset}\n{direction} na {percent:.2f}%\nBylo: ${was:,.2f}\nSeichas: ${now:,.2f}',
        'rose': 'Vyrosla',
        'fell': 'Upala',
        'menu_track': 'Otslezhivat aktiv',
        'menu_market': 'Rynochnyy obzor',
        'menu_chart': 'Analiz grafika',
        'menu_ai': 'Zadat vopros II',
    },
    'en': {
        'choose_lang': 'Choose language:',
        'welcome': 'Hello! I am Vortex. Your smart crypto assistant.',
        'track_choose': 'Choose cryptocurrency:',
        'tracking': 'Tracking {asset}\nPrice: ${price:,.2f}\n24h: {change:+.2f}%',
        'market_loading': 'Loading market data...',
        'ask_chart': 'Send chart screenshot',
        'analyzing': 'Analyzing chart...',
        'ask_ai': 'Ask me anything!',
        'thinking': 'Thinking...',
        'price_alert': 'Price changed!\n{asset}\n{direction} by {percent:.2f}%\nWas: ${was:,.2f}\nNow: ${now:,.2f}',
        'rose': 'Rose',
        'fell': 'Fell',
        'menu_track': 'Track asset',
        'menu_market': 'Market overview',
        'menu_chart': 'Chart analysis',
        'menu_ai': 'Ask AI',
    }
}

DB_NAME = "vortex.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                selected_asset TEXT,
                last_price REAL,
                chat_id INTEGER,
                language TEXT DEFAULT 'ru'
            )
        ''')
        await db.commit()

async def set_user_asset(user_id, asset, chat_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO users (user_id, selected_asset, last_price, chat_id)
            VALUES (?, ?, NULL, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                selected_asset = excluded.selected_asset,
                chat_id = excluded.chat_id,
                last_price = NULL
        ''', (user_id, asset, chat_id))
        await db.commit()

async def get_user_asset(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT selected_asset, last_price FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else (None, None)

async def update_user_price(user_id, price):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET last_price = ? WHERE user_id = ?", (price, user_id)
        )
        await db.commit()

async def get_all_tracking_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, selected_asset, last_price, chat_id FROM users WHERE selected_asset IS NOT NULL"
        ) as cursor:
            return await cursor.fetchall()

async def set_user_language(user_id, lang):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO users (user_id, language) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET language = excluded.language
        ''', (user_id, lang))
        await db.commit()

async def get_user_language(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_price(symbol):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": symbol}
        ) as resp:
            data = await resp.json()
            return {
                "price": float(data["lastPrice"]),
                "change_percent": float(data["priceChangePercent"])
            }

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def chat_with_ai(message_text):
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Vortex, friendly crypto AI assistant."},
                {"role": "user", "content": message_text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

async def analyze_image(image_base64):
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are crypto analyst. Analyze chart simply."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze chart"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

async def market_overview(prices_data):
    prompt = f"""You are Vortex analyst. Binance data:
{prices_data}
Give brief lively market overview."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

lang_inline = InlineKeyboardMarkup([
    [InlineKeyboardButton("RU", callback_data="lang_ru"),
     InlineKeyboardButton("ENG", callback_data="lang_en")]
])

crypto_inline = InlineKeyboardMarkup([
    [InlineKeyboardButton("Bitcoin", callback_data="asset_Bitcoin")],
    [InlineKeyboardButton("Ethereum", callback_data="asset_Ethereum")],
    [InlineKeyboardButton("Binance Coin", callback_data="asset_Binance Coin")],
    [InlineKeyboardButton("Solana", callback_data="asset_Solana")]
])

def get_main_menu(lang):
    t = TEXTS[lang]
    return ReplyKeyboardMarkup([
        [t['menu_track']], [t['menu_market']],
        [t['menu_chart']], [t['menu_ai']]
    ], resize_keyboard=True)

async def start(update, context):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    if lang is None:
        await update.message.reply_text(
            "Vyberite yazyk:\nChoose language:",
            reply_markup=lang_inline
        )
    else:
        await update.message.reply_text(
            TEXTS[lang]['welcome'],
            reply_markup=get_main_menu(lang)
        )

async def select_language(update, context):
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("lang_", "")
    await set_user_language(query.from_user.id, lang)
    await query.message.reply_text(
        TEXTS[lang]['welcome'],
        reply_markup=get_main_menu(lang)
    )

async def track_asset_handler(update, context, lang):
    await update.message.reply_text(TEXTS[lang]['track_choose'], reply_markup=crypto_inline)

async def process_asset(update, context):
    query = update.callback_query
    await query.answer()
    asset_name = query.data.replace("asset_", "")
    symbol = CRYPTO_SYMBOLS[asset_name]
    user_id = query.from_user.id
    await set_user_asset(user_id, asset_name, query.message.chat.id)
    data = await get_price(symbol)
    await update_user_price(user_id, data["price"])
    lang = await get_user_language(user_id) or 'ru'
    t = TEXTS[lang]
    await query.message.reply_text(
        t['tracking'].format(asset=asset_name, price=data['price'], change=data['change_percent'])
    )

async def market_summary_handler(update, context, lang):
    await update.message.reply_text(TEXTS[lang]['market_loading'])
    prices = {}
    for name, symbol in CRYPTO_SYMBOLS.items():
        data = await get_price(symbol)
        prices[name] = f"${data['price']:,.2f} ({data['change_percent']:+.2f}%)"
    overview = await market_overview(prices)
    await update.message.reply_text(overview)

async def ask_for_image_handler(update, context, lang):
    await update.message.reply_text(TEXTS[lang]['ask_chart'])

async def analyze_chart(update, context):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id) or 'ru'
    await update.message.reply_text(TEXTS[lang]['analyzing'])
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_obj = await file.download_as_bytearray()
    image_bytes = bytes(file_obj)
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    analysis = await analyze_image(image_base64)
    await update.message.reply_text(analysis)

async def ask_ai_mode_handler(update, context, lang):
    await update.message.reply_text(TEXTS[lang]['ask_ai'])

async def any_message_handler(update, context, lang):
    await update.message.reply_text(TEXTS[lang]['thinking'])
    answer = await chat_with_ai(update.message.text)
    await update.message.reply_text(answer)

async def handle_text(update, context):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id) or 'ru'
    text = update.message.text
    tr = TEXTS['ru']
    te = TEXTS['en']
    
    if text in [tr['menu_track'], te['menu_track']]:
        await track_asset_handler(update, context, lang)
    elif text in [tr['menu_market'], te['menu_market']]:
        await market_summary_handler(update, context, lang)
    elif text in [tr['menu_chart'], te['menu_chart']]:
        await ask_for_image_handler(update, context, lang)
    elif text in [tr['menu_ai'], te['menu_ai']]:
        await ask_ai_mode_handler(update, context, lang)
    else:
        await any_message_handler(update, context, lang)

async def check_prices(context):
    users = await get_all_tracking_users()
    for user_id, asset_name, last_price, chat_id in users:
        if not asset_name or not chat_id:
            continue
        symbol = CRYPTO_SYMBOLS.get(asset_name)
        if not symbol:
            continue
        try:
            data = await get_price(symbol)
            current_price = data["price"]
            if last_price is None:
                await update_user_price(user_id, current_price)
                continue
            change_percent = abs((current_price - last_price) / last_price * 100)
            if change_percent >= PRICE_CHANGE_THRESHOLD:
                lang = await get_user_language(user_id) or 'ru'
                t = TEXTS[lang]
                direction = t['rose'] if current_price > last_price else t['fell']
                await context.bot.send_message(
                    chat_id,
                    t['price_alert'].format(
                        asset=asset_name, direction=direction,
                        percent=change_percent, was=last_price, now=current_price
                    )
                )
                await update_user_price(user_id, current_price)
        except Exception as e:
            print(f"Error: {e}")

def setup_scheduler(application):
    application.job_queue.run_repeating(
        check_prices, interval=CHECK_INTERVAL_MINUTES * 60, first=10
    )

logging.basicConfig(level=logging.INFO)

def main():
    asyncio.run(init_db())
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(select_language, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(process_asset, pattern="^asset_"))
    application.add_handler(MessageHandler(filters.PHOTO, analyze_chart))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    setup_scheduler(application)
    print("Vortex started!")
    application.run_polling()

if __name__ == "__main__":
    main()
