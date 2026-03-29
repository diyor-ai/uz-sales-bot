# bot-backup.py — TO'LIQ VERSIYA
import os
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, 
                           MessageHandler, filters, ContextTypes, ConversationHandler)
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "Mahsulotlar"

SEARCH_STATE = 1  # ConversationHandler uchun

def get_products():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet.get_all_records()

def search_products(query, products):
    query = query.lower()
    return [p for p in products if 
            query in p['Nomi'].lower() or 
            query in p['Tavsif'].lower()]

# ===== MAIN MENU =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Barcha mahsulotlar", callback_data="show_products")],
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
    ]
    await update.message.reply_text(
        "👋 Assalomu alaykum! Uz-Sales botiga xush kelibsiz!\n\nNima qilmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== BUTTON HANDLER =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "show_products":
        products = get_products()
        keyboard = []
        for p in products:
            keyboard.append([InlineKeyboardButton(
                f"{p['Nomi']} — {p['Narxi']:,} so'm",
                callback_data=f"product_{p['ID']}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back")])
        await query.edit_message_text(
            "📦 Mahsulotni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("product_"):
        product_id = int(query.data.split("_")[1])
        products = get_products()
        p = next((x for x in products if x['ID'] == product_id), None)
        if p:
            text = (f"📦 *{p['Nomi']}*\n"
                    f"💰 Narxi: *{p['Narxi']:,} so'm*\n"
                    f"📝 {p['Tavsif']}\n"
                    f"📐 O'lchami: {p.get('Olchami', '—')}")
            keyboard = [
                [InlineKeyboardButton("🛒 Sotib olish", callback_data=f"buy_{product_id}")],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="show_products")]
            ]
            await query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    elif query.data.startswith("buy_"):
        product_id = query.data.split("_")[1]
        context.user_data['buying_product'] = product_id
        context.user_data['order_step'] = 'name'
        await query.edit_message_text(
            "🛒 Buyurtma berish\n\n"
            "Ismingizni kiriting:"
        )

    elif query.data == "search":
        context.user_data['order_step'] = 'searching'
        await query.edit_message_text("🔍 Qidiruv so'zini yozing (masalan: iphone, samsung):")

    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("📦 Barcha mahsulotlar", callback_data="show_products")],
            [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        ]
        await query.edit_message_text(
            "Nima qilmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ===== MESSAGE HANDLER (order flow + search) =====
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get('order_step')
    text = update.message.text

    # SEARCH
    if step == 'searching':
        products = get_products()
        found = search_products(text, products)
        if found:
            keyboard = [[InlineKeyboardButton(
                f"{p['Nomi']} — {p['Narxi']:,} so'm",
                callback_data=f"product_{p['ID']}"
            )] for p in found]
            keyboard.append([InlineKeyboardButton("🔙 Bosh sahifa", callback_data="back")])
            await update.message.reply_text(
                f"✅ {len(found)} ta natija topildi:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                "❌ Hech narsa topilmadi. Boshqacha so'z bilan urining.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Bosh sahifa", callback_data="back")]
                ])
            )
        context.user_data['order_step'] = None

    # ORDER FLOW
    elif step == 'name':
        context.user_data['order_name'] = text
        context.user_data['order_step'] = 'phone'
        await update.message.reply_text("📞 Telefon raqamingizni kiriting (+998 ...):")

    elif step == 'phone':
        context.user_data['order_phone'] = text
        context.user_data['order_step'] = 'address'
        await update.message.reply_text("📍 Manzilingizni kiriting:")

    elif step == 'address':
        context.user_data['order_address'] = text
        # Order tayyor
        order = {
            'name': context.user_data.get('order_name'),
            'phone': context.user_data.get('order_phone'),
            'address': text,
            'product_id': context.user_data.get('buying_product'),
        }
        confirm_text = (
            f"✅ Buyurtmangiz qabul qilindi!\n\n"
            f"👤 Ism: {order['name']}\n"
            f"📞 Tel: {order['phone']}\n"
            f"📍 Manzil: {order['address']}\n\n"
            f"Tez orada siz bilan bog'lanamiz! 🙏"
        )
        await update.message.reply_text(confirm_text)
        print(f"🆕 YANGI BUYURTMA: {order}")  # Day 5 da Sheetga yozamiz
        context.user_data['order_step'] = None

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()