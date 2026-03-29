# day3.py — ORDER FLOW

from day2 import search, show

orders = []  # Barcha orderlar shu yerda saqlanadi


def take_order(product):
    print(f"\n🛒 Siz tanlagan mahsulot: {product['Nomi']}")
    print(f"💰 Narxi: {product['Narxi']:,} so'm")
    print("-" * 40)

    # FLOW
    confirm = input("Sotib olasizmi? (ha/yo'q): ").lower()
    if confirm != "ha":
        print("❌ Bekor qilindi.")
        return

    ism = input("👤 Ismingiz: ")
    telefon = input("📞 Telefon (+998...): ")
    size = input("📐 O'lchami (S/M/L yoki yo'q): ")
    manzil = input("📍 Manzilingiz: ")

    order = {
        "mahsulot": product['Nomi'],
        "narx": product['Narxi'],
        "ism": ism,
        "telefon": telefon,
        "size": size,
        "manzil": manzil,
    }

    orders.append(order)

    print("\n" + "=" * 40)
    print("✅ BUYURTMA QABUL QILINDI!")
    print("=" * 40)
    print(f"📦 Mahsulot : {order['mahsulot']}")
    print(f"💰 Narx     : {order['narx']:,} so'm")
    print(f"👤 Ism      : {order['ism']}")
    print(f"📞 Telefon  : {order['telefon']}")
    print(f"📐 Size     : {order['size']}")
    print(f"📍 Manzil   : {order['manzil']}")
    print("=" * 40)
    print("🙏 Tez orada siz bilan bog'lanamiz!")


def main():
    print("🤖 Uz-Sales Bot (Terminal versiya)")
    print("=" * 40)

    while True:
        query = input("\n🔍 Nima qidiryapsiz? (q = chiqish): ").strip()

        if query.lower() == "q":
            print("👋 Xayr!")
            break

        found = search(query)

        if not found:
            print("❌ Topilmadi. Boshqacha yozing.")
            continue

        # Bir nechta natija bo'lsa — tanlash
        if len(found) == 1:
            take_order(found[0])
        else:
            print(f"\n✅ {len(found)} ta natija topildi:")
            for i, p in enumerate(found, 1):
                print(f"  {i}. {p['Nomi']} — {p['Narxi']:,} so'm")

            choice = input("\nQaysi birini tanlaysiz? (raqam): ").strip()

            if choice.isdigit() and 1 <= int(choice) <= len(found):
                take_order(found[int(choice) - 1])
            else:
                print("❌ Noto'g'ri tanlov.")


if __name__ == "__main__":
    main()