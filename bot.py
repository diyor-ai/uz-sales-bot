# bot.py — DAY 7+ versiya (Multi-client + Multi-language)

import os
import json
import time
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
load_dotenv()

# ================== SOZLAMALAR ==================
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
SCOPES           = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "credentials.json"
ORDERS_SHEET     = "Buyurtmalar"
CONFIGS_DIR      = "configs"
LOCALES_DIR      = "locales"
# ================================================


# ================== LOCALES ==================
def load_locales():
    locales = {}
    for file in os.listdir(LOCALES_DIR):
        if file.endswith(".json"):
            lang = file.replace(".json", "")
            with open(f"{LOCALES_DIR}/{file}", encoding="utf-8") as f:
                locales[lang] = json.load(f)
    return locales

LOCALES = load_locales()

def t(context, key):
    """Tarjima — context dan tilni oladi"""
    lang = context.user_data.get("lang", "uz")
    return LOCALES.get(lang, LOCALES["uz"]).get(key, key)
# =============================================


# ================== CLIENT CONFIG ==================
def load_clients():
    clients = {}
    for file in os.listdir(CONFIGS_DIR):
        if file.endswith(".json"):
            with open(f"{CONFIGS_DIR}/{file}", encoding="utf-8") as f:
                config = json.load(f)
                clients[config["client_id"]] = config
    return clients

CLIENTS = load_clients()
# ===================================================


# ================== CACHE ==================
_cache = {}
CACHE_TTL = 300

def get_products(sheet_name):
    now = time.time()
    if sheet_name in _cache:
        if (now - _cache[sheet_name]["last_updated"]) < CACHE_TTL:
            return _cache[sheet_name]["products"]
    creds  = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet  = client.open(sheet_name).sheet1
    _cache[sheet_name] = {
        "products":     sheet.get_all_records(),
        "last_updated": now
    }
    return _cache[sheet_name]["products"]
# ==========================================


# ================== SHEET ==================
def save_order(sheet_name, order):
    try:
        creds       = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client      = gspread.authorize(creds)
        spreadsheet = client.open(sheet_name)
        try:
            ws = spreadsheet.worksheet(ORDERS_SHEET)
        except:
            ws = spreadsheet.add_worksheet(ORDERS_SHEET, rows=1000, cols=10)
            ws.append_row(["Sana","Mahsulot","Narx","Ism","Telefon","Manzil","Til","Status"])
        ws.append_row([
            order["sana"], order["mahsulot"], order["narx"],
            order["ism"], order["telefon"], order["manzil"],
            order.get("til", "uz"), "Yangi"
        ])
        return True
    except Exception as e:
        print(f"Sheet xatosi: {e}")
        return False
# ==========================================


# ================== ADMIN ==================
async def notify_admin(context, order, admin_chat_id, shop_name):
    text = (
        f"🆕 YANGI BUYURTMA!\n"
        f"🏪 Shop : {shop_name}\n"
        f"🌍 Til  : {order.get('til','uz').upper()}\n"
        f"{'='*30}\n"
        f"📦 Mahsulot : {order['mahsulot']}\n"
        f"💰 Narx     : {order['narx']:,} so'm\n"
        f"👤 Ism      : {order['ism']}\n"
        f"📞 Telefon  : {order['telefon']}\n"
        f"📍 Manzil   : {order['manzil']}\n"
        f"🕐 Sana     : {order['sana']}\n"
        f"{'='*30}"
    )
    await context.bot.send_message(chat_id=admin_chat_id, text=text)
# ==========================================


# ================== HELPERS ==================
def search_products(query, products):
    query = query.lower()
    return [p for p in products if
            query in str(p.get('Nomi','')).lower() or
            query in str(p.get('Tavsif','')).lower()]

def format_price(price):
    return f"{int(price):,} so'm"

def get_client(context):
    client_id = context.user_data.get("client_id", "client_1")
    return CLIENTS.get(client_id)

def lang_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        ]
    ])

def shop_select_keyboard(context):
    keyboard = []
    for client_id, config in CLIENTS.items():
        keyboard.append([InlineKeyboardButton(
            f"🏪 {config['shop_name']}",
            callback_data=f"select_client_{client_id}"
        )])
    return InlineKeyboardMarkup(keyboard)

def main_menu_keyboard(context):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(context, "all_products"), callback_data="show_products")],
        [InlineKeyboardButton(t(context, "search"),       callback_data="search")],
    ])
# =============================================


# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Til tanlash"""
    await update.message.reply_text(
        "🌍 Tilni tanlang / Выберите язык / Choose language:",
        reply_markup=lang_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # TIL TANLASH
    if query.data.startswith("lang_"):
        lang = query.data.replace("lang_", "")
        context.user_data["lang"] = lang
        await query.edit_message_text(
            t(context, "choose_shop"),
            reply_markup=shop_select_keyboard(context)
        )

    # SHOP TANLASH
    elif query.data.startswith("select_client_"):
        client_id = query.data.replace("select_client_", "")
        context.user_data["client_id"] = client_id
        client = CLIENTS[client_id]
        await query.edit_message_text(
            f"🏪 *{client['shop_name']}*\n\n{t(context, 'welcome')}",
            reply_markup=main_menu_keyboard(context),
            parse_mode='Markdown'
        )

    # BACK
    elif query.data == "back":
        client = get_client(context)
        await query.edit_message_text(
            f"🏪 *{client['shop_name']}*",
            reply_markup=main_menu_keyboard(context),
            parse_mode='Markdown'
        )

    # BARCHA MAHSULOTLAR
    elif query.data == "show_products":
        client   = get_client(context)
        products = get_products(client['sheet_name'])
        keyboard = [[InlineKeyboardButton(
            f"{p['Nomi']}  💰 {format_price(p['Narxi'])}",
            callback_data=f"product_{p['ID']}"
        )] for p in products]
        keyboard.append([InlineKeyboardButton(t(context, "back"), callback_data="back")])
        await query.edit_message_text(
            f"🏪 *{client['shop_name']}*\n{t(context, 'choose_product')}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    # MAHSULOT DETAIL
    elif query.data.startswith("product_"):
        product_id = int(query.data.split("_")[1])
        client     = get_client(context)
        products   = get_products(client['sheet_name'])
        p = next((x for x in products if x['ID'] == product_id), None)
        if p:
            text = (
                f"📦 *{p['Nomi']}*\n\n"
                f"💰 {format_price(p['Narxi'])}\n"
                f"📝 {p['Tavsif']}\n\n"
                f"{t(context, 'buy_confirm')}"
            )
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(context, "yes"), callback_data=f"buy_{product_id}"),
                     InlineKeyboardButton(t(context, "no"),  callback_data="back")]
                ]),
                parse_mode='Markdown'
            )

    # SOTIB OLISH
    elif query.data.startswith("buy_"):
        product_id = int(query.data.split("_")[1])
        client     = get_client(context)
        products   = get_products(client['sheet_name'])
        p = next((x for x in products if x['ID'] == product_id), None)
        if p:
            context.user_data['order'] = {"mahsulot": p['Nomi'], "narx": p['Narxi']}
            context.user_data['step']  = 'ism'
            await query.edit_message_text(t(context, "ask_name"))

    # QIDIRISH
    elif query.data == "search":
        context.user_data['step'] = 'searching'
        await query.edit_message_text(t(context, "search_prompt"))

    # TIL O'ZGARTIRISH
    elif query.data == "change_lang":
        await query.edit_message_text(
            "🌍 Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=lang_keyboard()
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step   = context.user_data.get('step')
    text   = update.message.text
    client = get_client(context)

    # CONTACT
    if update.message.contact:
        phone = update.message.contact.phone_number
        context.user_data['order']['telefon'] = phone
        context.user_data['step'] = 'manzil'
        await update.message.reply_text(
            f"✅ {phone}\n\n{t(context, 'ask_address')}",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        return

    # SEARCH
    if step == 'searching':
        products = get_products(client['sheet_name'])
        found    = search_products(text, products)
        if found:
            keyboard = [[InlineKeyboardButton(
                f"{p['Nomi']}  💰 {format_price(p['Narxi'])}",
                callback_data=f"product_{p['ID']}"
            )] for p in found]
            keyboard.append([InlineKeyboardButton(t(context, "home"), callback_data="back")])
            await update.message.reply_text(
                f"✅ *{len(found)} {t(context, 'found')}:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(t(context, "not_found"))
        context.user_data['step'] = None

    elif step == 'ism':
        context.user_data['order']['ism'] = text
        context.user_data['step'] = 'telefon'
        keyboard = [[KeyboardButton(t(context, "share_phone"), request_contact=True)]]
        await update.message.reply_text(
            t(context, "ask_phone"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        )

    elif step == 'telefon':
        context.user_data['order']['telefon'] = text
        context.user_data['step'] = 'manzil'
        await update.message.reply_text(
            t(context, "ask_address"),
            reply_markup=ReplyKeyboardRemove()
        )

    elif step == 'manzil':
        order           = context.user_data['order']
        order['manzil'] = text
        order['sana']   = datetime.now().strftime("%Y-%m-%d %H:%M")
        order['til']    = context.user_data.get("lang", "uz")

        save_order(client['sheet_name'], order)
        await notify_admin(context, order, client['admin_chat_id'], client['shop_name'])

        await update.message.reply_text(
            f"{t(context, 'order_done')}\n\n"
            f"📦 {order['mahsulot']}\n"
            f"💰 {format_price(order['narx'])}\n"
            f"👤 {order['ism']}\n"
            f"📞 {order['telefon']}\n"
            f"📍 {order['manzil']}",
            reply_markup=main_menu_keyboard(context)
        )
        context.user_data['step']  = None
        context.user_data['order'] = {}


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.CONTACT, message_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("🤖 Bot ishga tushdi... (Multi-client + Multi-language)")
    app.run_polling()

if __name__ == "__main__":
    main()