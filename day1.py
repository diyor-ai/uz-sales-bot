import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "Mahsulotlar"

creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open(SHEET_NAME).sheet1
data = sheet.get_all_records()

print("✅ DAY 1 — Muvaffaqiyatli! 10 ta mahsulot terminalda:\n")
for row in data:
    print(f"🆔 {row['ID']} | 📦 {row['Nomi']}")
    print(f"   💰 Narxi: {row['Narxi']} so‘m")
    print(f"   📝 {row['Tavsif']}")
    print("-" * 60)
