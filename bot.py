# bot.py — FINAL VERSION (Railway ready)

import os
import json
import time
import re
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

# ================== SOZLAMALAR ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SCOPES         = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
ORDERS_SHEET   = "Buyurtmalar"
CONFIGS_DIR    = "configs"
LOCALES_DIR    = "locales"
# ================================================


# ================== CREDENTIALS ==================
def get_credentials():
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json:
        return Credentials.from_service_account_info(
            json.loads(creds_json), scopes=SCOPES
        )
    return Credentials.from_service_account_file(
        "credentials.json", scopes=SCOPES
    )
# =================================================


# ================== RATE LIMITING ==================
user_last_action = {}

def rate_limit_check(user_id, seconds=2):
    now = time.time()
    if user_id in user_last_action:
        if (now - user_last_action[user_id]) < seconds:
            return False
    user_last_action[user_id] = now
    return True
# ===================================================


# ================== LOCALES ==================
def load_locales():
    locales = {}
    try:
        for file in os.listdir(LOCALES_DIR):
            if file.endswith(".json"):
                lang = file.replace(".json", "")
                with open(f"{LOCALES_DIR}/{file}", encoding="utf-8") as f:
                    locales[lang] = json.load(f)
    except Exception as e:
        print(f"Locale load error: {e}")
    return locales

LOCALES = load_locales()

def t(context, key):
    lang = context.user_data.get("lang", "uz")
    return LOCALES.get(lang, LOCALES.get("uz", {})).get(key, key)
# =============================================


# ================== CLIENT CONFIG ==================
def load_clients():
    clients = {}
    try:
        # Railway: Environment Variable dan
        i = 1
        while True:
            config_str = os.getenv(f"CLIENT_{i}")
            if not config_str:
                break
            config = json.loads(config_str)
            clients[config["client_id"]] = config
            i += 1

        # Local: configs/ papkadan
        if not clients and os.path.exists(CONFIGS_DIR):
            for file in os.listdir(CONFIGS_DIR):
                if file.endswith(".json"):
                    with open(f"{CONFIGS_DIR}/{file}", encoding="utf-8") as f:
                        config = json.load(f)
                        clients[config["client_id"]] = config

    except Exception as e:
        print(f"Client config load error: {e}")
    return clients

CLIENTS = load_clients()
# ===================================================


# ================== CACHE ==================
_cache = {}
CACHE_TTL = 60

def get_products(sheet_name):
    now = time.time()
    if sheet_name in _cache:
        if (now - _cache[sheet_name]["last_updated"]) < CACHE_TTL:
            return _cache[sheet_name]["products"]
    try:
        creds  = get_credentials()
        client = gspread.authorize(creds)
        sheet  = client.open(sheet_name).sheet1
        _cache[sheet_name] = {
            "products":     sheet.get_all_records(),
            "last_updated": now
        }
        return _cache[sheet_name]["products"]
    except Exception as e:
        print(f"Sheet error: {e}")
        return []
# ==========================================


# ================== VALIDATION ==================
def validate_phone(phone):
    phone = phone.strip().replace(" ", "").replace("-", "")
    patterns = [r'^\+998\d{9}$', r'^998\d{9}$', r'^9\d{8}$']
    for pattern in patterns:
        if re.match(pattern, phone):
            if not phone.startswith("+"):
                phone = "+998" + phone if not phone.startswith("998") else "+" + phone
            return phone
    return None

def sanitize(text):
    return text.replace("<", "&lt;").replace(">", "&gt;").strip()
# ===============================================


# ================== SHEET ==================
def save_order(sheet_name, order):
    try:
        creds       = get_credentials()
        client      = gspread.authorize(creds)
        spreadsheet = client.open(sheet_name)
        try:
            ws = spreadsheet.worksheet(ORDERS_SHEET)
        except Exception:
            ws = spreadsheet.add_worksheet(ORDERS_SHEET, rows=1000, cols=10)
            ws.append_row(["Sana", "Mahsulot", "Narx", "Ism", "Telefon", "Manzil", "Til", "Status"])
        ws.append_row([
            order["sana"], order["mahsulot"], order["narx"],
            order["ism"], order["telefon"], order["manzil"],
            order.get("til", "uz"), "Yangi"
        ])
        return True
    except Exception as e:
        print(f"Sheet save error: {e}")
        return False
# ==========================================


# ================== ADMIN ==================
async def notify_admin(context, order, admin_chat_id, shop_name):
    try:
        text = (
            f"\U0001f195 YANGI BUYURTMA!\n"
            f"\U0001f3ea Shop : {shop_name}\n"
            f"\U0001f30d Til  : {order.get('til', 'uz').upper()}\n"
            f"{'=' * 30}\n"
            f"\U0001f4e6 Mahsulot : {order['mahsulot']}\n"
            f"\U0001f4b0 Narx     : {order['narx']:,} so'm\n"
            f"\U0001f464 Ism      : {order['ism']}\n"
            f"\U0001f4de Telefon  : {order['telefon']}\n"
            f"\U0001f4cd Manzil   : {order['manzil']}\n"
            f"\U0001f55c Sana     : {order['sana']}\n"
            f"{'=' * 30}"
        )
        await context.bot.send_message(chat_id=admin_chat_id, text=text)
    except Exception as e:
        print(f"Admin notify error: {e}")
# ==========================================


# ================== HELPERS ==================
def search_products(query, products):
    query = query.lower()
    return [p for p in products if
            query in str(p.get('Nomi', '')).lower() or
            query in str(p.get('Tavsif', '')).lower()]

def format_price(price):
    return f"{int(price):,} so'm"

def get_client(context):
    client_id = context.user_data.get("client_id", "client_1")
    return CLIENTS.get(client_id)

def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("\U0001f1fa\U0001f1ff O'zbek",  callback_data="lang_uz"),
        InlineKeyboardButton("\U0001f1f7\U0001f1fa \u0420\u0443\u0441\u0441\u043a\u0438\u0439", callback_data="lang_ru"),
        InlineKeyboardButton("\U0001f1ec\U0001f1e7 English", callback_data="lang_en"),
    ]])

def shop_select_keyboard():
    keyboard = []
    for client_id, config in CLIENTS.items():
        keyboard.append([InlineKeyboardButton(
            f"\U0001f3ea {config['shop_name']}",
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
    await update.message.reply_text(
        "\U0001f30d Tilni tanlang / \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u044f\u0437\u044b\u043a / Choose language:",
        reply_markup=lang_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not rate_limit_check(update.effective_user.id):
        return

    # TIL TANLASH
    if query.data.startswith("lang_"):
        lang = query.data.replace("lang_", "")
        context.user_data["lang"] = lang
        await query.edit_message_text(
            t(context, "choose_shop"),
            reply_markup=shop_select_keyboard()
        )

    # SHOP TANLASH
    elif query.data.startswith("select_client_"):
        client_id = query.data.replace("select_client_", "")
        context.user_data["client_id"] = client_id
        client = CLIENTS[client_id]
        await query.edit_message_text(
            f"\U0001f3ea *{client['shop_name']}*\n\n{t(context, 'welcome')}",
            reply_markup=main_menu_keyboard(context),
            parse_mode='Markdown'
        )

    # BACK
    elif query.data == "back":
        client = get_client(context)
        await query.edit_message_text(
            f"\U0001f3ea *{client['shop_name']}*",
            reply_markup=main_menu_keyboard(context),
            parse_mode='Markdown'
        )

    # BARCHA MAHSULOTLAR
    elif query.data == "show_products":
        client   = get_client(context)
        products = get_products(client['sheet_name'])
        if not products:
            await query.edit_message_text("\u274c Mahsulotlar topilmadi")
            return
        keyboard = [[InlineKeyboardButton(
            f"{p['Nomi']}  \U0001f4b0 {format_price(p['Narxi'])}",
            callback_data=f"product_{p['ID']}"
        )] for p in products]
        keyboard.append([InlineKeyboardButton(t(context, "back"), callback_data="back")])
        await query.edit_message_text(
            f"\U0001f3ea *{client['shop_name']}*\n{t(context, 'choose_product')}",
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
                f"\U0001f4e6 *{p['Nomi']}*\n\n"
                f"\U0001f4b0 {format_price(p['Narxi'])}\n"
                f"\U0001f4dd {p['Tavsif']}\n\n"
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

    # TASDIQLASH
    elif query.data == "confirm_order":
        order  = context.user_data.get('pending_order')
        client = get_client(context)
        if order:
            save_order(client['sheet_name'], order)
            await notify_admin(context, order, client['admin_chat_id'], client['shop_name'])
            await query.edit_message_text(
                f"{t(context, 'order_done')}\n\n"
                f"\U0001f4e6 {order['mahsulot']}\n"
                f"\U0001f4b0 {format_price(order['narx'])}\n"
                f"\U0001f464 {order['ism']}\n"
                f"\U0001f4de {order['telefon']}\n"
                f"\U0001f4cd {order['manzil']}\n\n"
                f"\U0001f64f Tez orada bog'lanamiz!",
                reply_markup=main_menu_keyboard(context)
            )
            context.user_data['step']          = None
            context.user_data['order']         = {}
            context.user_data['pending_order'] = None

    # BEKOR QILISH
    elif query.data == "cancel_order":
        await query.edit_message_text(
            t(context, "order_cancelled"),
            reply_markup=main_menu_keyboard(context)
        )
        context.user_data['step']          = None
        context.user_data['order']         = {}
        context.user_data['pending_order'] = None

    # QIDIRISH
    elif query.data == "search":
        context.user_data['step'] = 'searching'
        await query.edit_message_text(t(context, "search_prompt"))


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step   = context.user_data.get('step')
    text   = update.message.text
    client = get_client(context)

    # CONTACT
    if update.message.contact:
        phone     = update.message.contact.phone_number
        validated = validate_phone(phone)
        if validated:
            context.user_data['order']['telefon'] = validated
            context.user_data['step'] = 'manzil'
            await update.message.reply_text(
                f"\u2705 {validated}\n\n{t(context, 'ask_address')}",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(t(context, "invalid_phone"))
        return

    # STEP YO'Q → START GA
    if not step:
        await start(update, context)
        return

    # SEARCH
    if step == 'searching':
        products = get_products(client['sheet_name'])
        found    = search_products(sanitize(text), products)
        if found:
            keyboard = [[InlineKeyboardButton(
                f"{p['Nomi']}  \U0001f4b0 {format_price(p['Narxi'])}",
                callback_data=f"product_{p['ID']}"
            )] for p in found]
            keyboard.append([InlineKeyboardButton(t(context, "home"), callback_data="back")])
            await update.message.reply_text(
                f"\u2705 *{len(found)} {t(context, 'found')}:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(t(context, "not_found"))
        context.user_data['step'] = None

    # ISM
    elif step == 'ism':
        context.user_data['order']['ism'] = sanitize(text)
        context.user_data['step'] = 'telefon'
        keyboard = [[KeyboardButton(t(context, "share_phone"), request_contact=True)]]
        await update.message.reply_text(
            t(context, "ask_phone"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        )

    # TELEFON
    elif step == 'telefon':
        validated = validate_phone(text)
        if validated:
            context.user_data['order']['telefon'] = validated
            context.user_data['step'] = 'manzil'
            await update.message.reply_text(
                t(context, "ask_address"),
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(t(context, "invalid_phone"))

    # MANZIL → TASDIQLASH
    elif step == 'manzil':
        order           = context.user_data['order']
        order['manzil'] = sanitize(text)
        order['sana']   = datetime.now().strftime("%Y-%m-%d %H:%M")
        order['til']    = context.user_data.get("lang", "uz")

        context.user_data['pending_order'] = order

        await update.message.reply_text(
            f"\U0001f4cb *{t(context, 'confirm_order')}*\n\n"
            f"\U0001f4e6 {order['mahsulot']}\n"
            f"\U0001f4b0 {format_price(order['narx'])}\n"
            f"\U0001f464 {order['ism']}\n"
            f"\U0001f4de {order['telefon']}\n"
            f"\U0001f4cd {order['manzil']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("\u2705 Tasdiqlash",   callback_data="confirm_order")],
                [InlineKeyboardButton("\u274c Bekor qilish", callback_data="cancel_order")]
            ]),
            parse_mode='Markdown'
        )


# ================== MAIN ==================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.CONTACT, message_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 Bot ishga tushdi... (FINAL VERSION)")
    app.run_polling()

if __name__ == "__main__":
    main()