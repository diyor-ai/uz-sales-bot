# bot.py — DAY 7 versiya (Multi-client)

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
CREDENTIALS_FILE = "credentials.json"
SCOPES           = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
ORDERS_SHEET     = "Buyurtmalar"
CONFIGS_DIR      = "configs"
# ================================================


# ================== CLIENT CONFIG ==================
def load_clients():
    """Barcha client configlarni yuklaydi"""
    clients = {}
    for file in os.listdir(CONFIGS_DIR):
        if file.endswith(".json"):
            with open(f"{CONFIGS_DIR}/{file}") as f:
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
            ws.append_row(["Sana","Mahsulot","Narx","Ism","Telefon","Manzil","Status"])
        ws.append_row([
            order["sana"], order["mahsulot"], order["narx"],
            order["ism"], order["telefon"], order["manzil"], "Yangi"
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
        f"🏪 Shop: {shop_name}\n"
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
    """User tanlagan clientni qaytaradi"""
    client_id = context.user_data.get("client_id", "client_1")
    return CLIENTS.get(client_id)

def main_menu_keyboard(shop_name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Barcha mahsulotlar", callback_data="show_products")],
        [InlineKeyboardButton("🔍 Qidirish",           callback_data="search")],
    ])

def shop_select_keyboard():
    """Client tanlash tugmalari"""
    keyboard = []
    for client_id, config in CLIENTS.items():
        keyboard.append([InlineKeyboardButton(
            f"🏪 {config['shop_name']}",
            callback_data=f"select_client_{client_id}"
        )])
    return InlineKeyboardMarkup(keyboard)
# =============================================


# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shop tanlash"""
    await update.message.reply_text(
        "👋 *Assalomu alaykum!*\n\nQaysi shopga kirasiz?",
        reply_markup=shop_select_keyboard(),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # SHOP TANLASH
    if query.data.startswith("select_client_"):
        client_id = query.data.replace("select_client_", "")
        context.user_data["client_id"] = client_id
        client = CLIENTS[client_id]
        await query.edit_message_text(
            f"🏪 *{client['shop_name']}* ga xush kelibsiz!\n\nNima qilmoqchisiz?",
            reply_markup=main_menu_keyboard(client['shop_name']),
            parse_mode='Markdown'
        )

    # BACK
    elif query.data == "back":
        client = get_client(context)
        await query.edit_message_text(
            f"🏪 *{client['shop_name']}*\n\nNima qilmoqchisiz?",
            reply_markup=main_menu_keyboard(client['shop_name']),
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
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back")])
        await query.edit_message_text(
            f"🏪 *{client['shop_name']}*\n📦 Mahsulotni tanlang:",
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
                f"💰 Narxi: *{format_price(p['Narxi'])}*\n"
                f"📝 {p['Tavsif']}\n\n"
                f"Sotib olasizmi?"
            )
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Ha",   callback_data=f"buy_{product_id}"),
                     InlineKeyboardButton("❌ Yo'q", callback_data="back")]
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
            await query.edit_message_text("👤 *Ismingizni kiriting:*", parse_mode='Markdown')

    # QIDIRISH
    elif query.data == "search":
        context.user_data['step'] = 'searching'
        await query.edit_message_text(
            "🔍 Qidiruv so'zini yozing:\n_Masalan: iphone, televizor_",
            parse_mode='Markdown'
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
            f"✅ {phone}\n\n📍 *Manzilingizni kiriting:*",
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
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back")])
            await update.message.reply_text(
                f"✅ *{len(found)} ta natija:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Topilmadi. Boshqacha yozing.")
        context.user_data['step'] = None

    elif step == 'ism':
        context.user_data['order']['ism'] = text
        context.user_data['step'] = 'telefon'
        keyboard = [[KeyboardButton("📞 Raqamni ulashish", request_contact=True)]]
        await update.message.reply_text(
            "📞 *Telefon raqamingiz:*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
            parse_mode='Markdown'
        )

    elif step == 'telefon':
        context.user_data['order']['telefon'] = text
        context.user_data['step'] = 'manzil'
        await update.message.reply_text(
            "📍 *Manzilingizni kiriting:*",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )

    elif step == 'manzil':
        order          = context.user_data['order']
        order['manzil'] = text
        order['sana']   = datetime.now().strftime("%Y-%m-%d %H:%M")

        save_order(client['sheet_name'], order)
        await notify_admin(context, order, client['admin_chat_id'], client['shop_name'])

        await update.message.reply_text(
            f"✅ *Buyurtmangiz qabul qilindi!*\n\n"
            f"📦 {order['mahsulot']}\n"
            f"💰 {format_price(order['narx'])}\n"
            f"👤 {order['ism']}\n"
            f"📞 {order['telefon']}\n"
            f"📍 {order['manzil']}\n\n"
            f"🙏 Tez orada bog'lanamiz!",
            reply_markup=main_menu_keyboard(client['shop_name']),
            parse_mode='Markdown'
        )
        context.user_data['step']  = None
        context.user_data['order'] = {}


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.CONTACT, message_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("🤖 Bot ishga tushdi... (DAY 7 — Multi-client)")
    app.run_polling()

if __name__ == "__main__":
    main()