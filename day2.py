# day2.py — CORE SEARCH LOGIC
from day1 import get_products


def search(user_input):
    products = get_products()
    user_input = user_input.lower()
    results = []

    for p in products:
        # Mahsulot nomi yoki tavsifida so'z bormi?
        if (user_input in p['Nomi'].lower() or
                user_input in p['Tavsif'].lower()):
            results.append(p)

    return results


def show(p):
    print(f"\n📦 {p['Nomi']}")
    print(f"💰 Narxi: {p['Narxi']:,} so'm")
    print(f"📝 {p['Tavsif']}")
    print("-" * 40)


# ===== TEST =====
test_queries = [
    "iphone",
    "samsung",
    "narxi qancha",  # topilmaydi — keyingi bosqich
    "televizor",
    "noise",  # tavsifdan topadi
]

for q in test_queries:
    print(f"\n🔍 Query: '{q}'")
    found = search(q)
    if found:
        for p in found:
            show(p)
    else:
        print("❌ Topilmadi")