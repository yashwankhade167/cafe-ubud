"""
Cafe Ubud — Database Models
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    slug = db.Column(db.String(50), nullable=False, unique=True)
    sort_order = db.Column(db.Integer, default=0)
    items = db.relationship("MenuItem", backref="category", lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug}


class MenuItem(db.Model):
    __tablename__ = "menu_items"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)
    emoji = db.Column(db.String(10), default="☕")
    tag = db.Column(db.String(50), default="")
    image_url = db.Column(db.String(300), default="")   # uploaded photo path
    is_available = db.Column(db.Boolean, default=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order_items = db.relationship("OrderItem", backref="menu_item", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "emoji": self.emoji,
            "tag": self.tag,
            "image_url": self.image_url,
            "is_available": self.is_available,
            "category": self.category.slug if self.category else None,
        }


class Table(db.Model):
    __tablename__ = "tables"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False, unique=True)
    qr_token = db.Column(db.String(64), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    orders = db.relationship("Order", backref="table", lazy=True)

    def to_dict(self):
        return {"id": self.id, "number": self.number, "qr_token": self.qr_token}


ORDER_STATUSES = [
    "pending", "accepted", "preparing", "cooking",
    "quality_check", "ready", "served", "completed", "cancelled"
]

PAYMENT_STATUSES = ["unpaid", "paid", "refunded"]


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"), nullable=True)
    customer_name = db.Column(db.String(120), default="")
    customer_phone = db.Column(db.String(20), default="")
    status = db.Column(db.String(30), default="pending")
    payment_status = db.Column(db.String(20), default="unpaid")
    razorpay_order_id = db.Column(db.String(100), default="")
    razorpay_payment_id = db.Column(db.String(100), default="")
    total_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "table_number": self.table.number if self.table else None,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "status": self.status,
            "payment_status": self.payment_status,
            "total_amount": self.total_amount,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "items": [i.to_dict() for i in self.items],
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price_at_order = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.menu_item.name if self.menu_item else "Unknown",
            "emoji": self.menu_item.emoji if self.menu_item else "🍽️",
            "quantity": self.quantity,
            "price_at_order": self.price_at_order,
            "subtotal": round(self.price_at_order * self.quantity, 2),
        }


class Reservation(db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    guests = db.Column(db.Integer, default=2)
    special_requests = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending")
    whatsapp_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "date": self.date,
            "time": self.time,
            "guests": self.guests,
            "special_requests": self.special_requests,
            "status": self.status,
            "whatsapp_sent": self.whatsapp_sent,
            "created_at": self.created_at.isoformat(),
        }


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    unit = db.Column(db.String(20), default="kg")
    quantity = db.Column(db.Float, default=0.0)
    low_stock_threshold = db.Column(db.Float, default=5.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "unit": self.unit,
            "quantity": self.quantity,
            "low_stock_threshold": self.low_stock_threshold,
            "is_low": self.quantity <= self.low_stock_threshold,
        }


class AdminUser(db.Model):
    __tablename__ = "admin_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)
