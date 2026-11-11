"""
Cafe Ubud — Database Seeder
============================
Populates a fresh database with starter data: categories, menu items,
tables (with QR tokens), an admin login, and a couple of sample
reservations/inventory rows so the dashboard isn't empty on first run.

Run with:  python seed.py
"""

import os
import secrets
from app import create_app
from models import db, Category, MenuItem, Table, AdminUser, InventoryItem, Reservation


def seed():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # ---- Categories -------------------------------------------------
        categories = {
            "coffee":  Category(name="Hot Coffee", slug="coffee", sort_order=1),
            "cold":    Category(name="Cold Brew",   slug="cold",   sort_order=2),
            "food":    Category(name="Food",        slug="food",   sort_order=3),
            "dessert": Category(name="Desserts",    slug="dessert", sort_order=4),
        }
        db.session.add_all(categories.values())
        db.session.flush()  # so categories get IDs before menu items reference them

        # ---- Menu items ---------------------------------------------------
        menu_data = [
            ("coffee", "☕", "Bali Sunrise Latte", "Single-origin Kintamani espresso with steamed oat milk & turmeric foam", 249, "Signature"),
            ("coffee", "🫖", "Ubud Cardamom Brew", "Slow-extracted filter coffee with hand-ground cardamom & honey", 199, "Hot Coffee"),
            ("coffee", "☕", "Monsoon Malabar", "Bold Arabica with caramelised notes, served black or with coconut cream", 219, "Single Origin"),
            ("cold", "🥤", "Iced Coconut Cold Brew", "18-hour cold brew steeped with toasted coconut & vanilla", 279, "Cold Brew"),
            ("cold", "🧊", "Chocolate Cascara", "Cascara tea chilled with dark chocolate drizzle & salt caramel", 259, "Cold Brew"),
            ("cold", "🍓", "Hibiscus Affogato", "Espresso poured over hibiscus gelato, finished with rose water mist", 299, "Specialty"),
            ("food", "🍕", "Balinese Chicken Pizza", "Thin sourdough base, sambal sauce, free-range chicken & fresh basil", 449, "Pizza"),
            ("food", "🍔", "Mushroom Truffle Burger", "House-patty with black truffle aioli, caramelised onion & brioche bun", 379, "Burger"),
            ("dessert", "🍰", "Ubud Tiramisu", "Mascarpone layered with Kintamani espresso-soaked ladyfingers", 219, "Classic"),
            ("dessert", "🍮", "Pandan Crème Brûlée", "Silky pandan custard with caramelised sugar crust", 239, "Chef's Special"),
        ]
        for slug, emoji, name, desc, price, tag in menu_data:
            db.session.add(MenuItem(
                name=name, description=desc, price=price, emoji=emoji, tag=tag,
                category_id=categories[slug].id
            ))

        # ---- Tables (with unique QR tokens) --------------------------------
        for n in range(1, 13):  # 12 tables to start
            db.session.add(Table(number=n, qr_token=secrets.token_urlsafe(8)))

        # ---- Admin login ----------------------------------------------------
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        generated_password = False
        if not admin_password:
            admin_password = secrets.token_urlsafe(9)
            generated_password = True

        admin = AdminUser(username=admin_username)
        admin.set_password(admin_password)
        db.session.add(admin)

        # ---- Sample inventory -----------------------------------------------
        inventory_data = [
            ("Coffee Beans (Kintamani)", "kg", 18, 5),
            ("Whole Milk", "l", 22, 8),
            ("Oat Milk", "l", 6, 5),
            ("Dark Chocolate", "kg", 4, 3),
            ("Pizza Dough Base", "packets", 30, 10),
            ("Mascarpone Cheese", "kg", 3, 2),
        ]
        for name, unit, qty, threshold in inventory_data:
            db.session.add(InventoryItem(name=name, unit=unit, quantity=qty, low_stock_threshold=threshold))

        # ---- Sample reservation ----------------------------------------------
        db.session.add(Reservation(
            name="Aarav Mehta", phone="+91 98765 11122", date="2026-06-25",
            time="19:30", guests=4, special_requests="Anniversary dinner, window seat preferred",
            status="pending"
        ))

        db.session.commit()
        print("Database seeded successfully.")
        print(f"   {len(menu_data)} menu items, {len(categories)} categories, 12 tables.")
        if generated_password:
            print(f"   Admin login -> username: {admin_username} | password: {admin_password}")
            print("   (No ADMIN_PASSWORD env var was set, so a random one was generated — save it now!)")
        else:
            print(f"   Admin login -> username: {admin_username} | password: (from ADMIN_PASSWORD env var)")


if __name__ == "__main__":
    seed()
