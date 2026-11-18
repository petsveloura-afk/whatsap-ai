import uuid, datetime as dt
from sqlalchemy import false, true, String, Integer, Float, Boolean, ForeignKey, JSON, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
def _id(): return str(uuid.uuid4())
def _now(): return dt.datetime.now(dt.timezone.utc)
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    whatsapp_consent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
class SearchConfig(Base):
    __tablename__ = "search_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    required_keywords: Mapped[list] = mapped_column(JSON, default=list)
    excluded_keywords: Mapped[list] = mapped_column(JSON, default=list)
    min_score: Mapped[int] = mapped_column(Integer, default=60)
    weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    search_id: Mapped[str] = mapped_column(ForeignKey("search_configs.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    extracted: Mapped[dict] = mapped_column(JSON)
    score: Mapped[int] = mapped_column(Integer)
    score_detail: Mapped[dict] = mapped_column(JSON)
    risks: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="new")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

class TelegramSource(Base):
    __tablename__ = "telegram_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    search_id: Mapped[str] = mapped_column(ForeignKey("search_configs.id"))
    code: Mapped[str] = mapped_column(String(32), unique=True)
    chat_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
class PasswordReset(Base):
    __tablename__ = "password_resets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    plan: Mapped[str] = mapped_column(String(20), default="starter")
    status: Mapped[str] = mapped_column(String(20), default="none")
    paypal_subscription_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    # v3.15: prepaid (card / one-time PayPal) access. NULL = no expiry (recurring PayPal subscription managed by webhooks).
    current_period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_period: Mapped[str | None] = mapped_column(String(10), nullable=True)  # monthly | yearly
    renewal_reminded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class Payment(Base):
    """v3.15: one row per payment attempt/receipt. Deliberately has NO foreign key and NO column named user_id:
    accounting records must be kept (7 years in Israel) even after the customer deletes the account, so the generic
    account purge must not remove them. The customer's e-mail is snapshotted for the receipt."""
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    customer_id: Mapped[str] = mapped_column(String(36), index=True)
    customer_email: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(20))
    period: Mapped[str] = mapped_column(String(10))            # monthly | yearly
    amount: Mapped[str] = mapped_column(String(16))            # decimal string, e.g. "99.00" (never a float)
    currency: Mapped[str] = mapped_column(String(3), default="ILS")
    method: Mapped[str] = mapped_column(String(16), default="card")   # card | paypal | subscription
    status: Mapped[str] = mapped_column(String(16), default="created", index=True)  # created | pending | completed | failed | refunded
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    payer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    card_brand: Mapped[str | None] = mapped_column(String(24), nullable=True)
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    receipt_no: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    period_start: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    refunded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class PaymentEvent(Base):
    __tablename__ = "payment_transactions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

class UserPreference(Base):
    __tablename__ = "user_preferences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    personalization_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

class AiMemory(Base):
    """Per-user memory. Always queried with user_id filter - never shared across users."""
    __tablename__ = "ai_memory"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # saved | rejected
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
