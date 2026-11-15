import uuid, datetime as dt
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON, DateTime, Text, UniqueConstraint
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
