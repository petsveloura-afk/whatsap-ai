"""Growth / scale / security tables (v3.1). All free: stored in the same database, no external service.
api_keys, webhook_endpoints, webhook_deliveries, referrals, shared_links, user_flags, market_observations,
rate_hits (shared rate limiter), error_events (self-hosted error tracking)."""
import datetime as dt
from sqlalchemy import String, Integer, Float, Boolean, JSON, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import _id, _now
from .models2 import _ts, _uid

class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    name: Mapped[str] = mapped_column(String(60))
    prefix: Mapped[str] = mapped_column(String(12), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256; the secret itself is shown once and never stored
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = _ts()

class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    url: Mapped[str] = mapped_column(String(1000))
    secret: Mapped[str] = mapped_column(String(64))
    min_score: Mapped[int] = mapped_column(Integer, default=60)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    cursor_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = _ts()

class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    endpoint_id: Mapped[str] = mapped_column(String(36), index=True)
    listing_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|ok|failed
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[dt.datetime] = _ts()

class Referral(Base):
    __tablename__ = "referrals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()  # the referrer / code owner
    code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)  # set only on the owner row
    referred_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)  # null = the code row itself
    created_at: Mapped[dt.datetime] = _ts()

class SharedLink(Base):
    __tablename__ = "shared_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    listing_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = _ts()

class UserFlag(Base):
    """Per-user opt-ins, e.g. 'market_pool' (share anonymised price points), 'weekly_digest'."""
    __tablename__ = "user_flags"
    __table_args__ = (UniqueConstraint("user_id", "name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    name: Mapped[str] = mapped_column(String(40))
    value: Mapped[bool] = mapped_column(Boolean, default=False)

class MarketObservation(Base):
    """Anonymised price point (no text, no user id) - only written for users who opted in to 'market_pool'."""
    __tablename__ = "market_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    category: Mapped[str] = mapped_column(String(40), index=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    rooms: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[dt.datetime] = _ts()

class RateHit(Base):
    __tablename__ = "rate_hits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    key: Mapped[str] = mapped_column(String(200), index=True)
    at: Mapped[float] = mapped_column(Float, index=True)  # unix seconds

class ErrorEvent(Base):
    __tablename__ = "error_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    fingerprint: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(String(300))
    route: Mapped[str] = mapped_column(String(200))
    count: Mapped[int] = mapped_column(Integer, default=1)
    sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen: Mapped[dt.datetime] = _ts()
    last_seen: Mapped[dt.datetime] = _ts()
