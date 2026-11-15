"""Additional spec tables. Wired in code: data_sources, ingestion_events, agent_jobs, agent_events,
notifications, notification_preferences, system_settings, admin_actions, user_profiles, roles, permissions,
user_listing_actions, listing_scores, listing_deduplication, listing_images, ai_embeddings.
Schema-ready (no runtime logic yet): search_sources, integrations, integration_sessions, whatsapp_connections."""
import datetime as dt
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import _id, _now

def _ts(): return mapped_column(DateTime(timezone=True), default=_now)
def _uid(unique=False, nullable=False): return mapped_column(ForeignKey("users.id"), index=not unique, unique=unique, nullable=nullable)

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("role", "permission"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    role: Mapped[str] = mapped_column(String(30), index=True)
    permission: Mapped[str] = mapped_column(String(60))
class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid(unique=True)
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="he")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Jerusalem")
class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    search_id: Mapped[str] = mapped_column(ForeignKey("search_configs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # rss | jsonfeed
    url: Mapped[str] = mapped_column(String(1000))
    interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="NEW")  # NEW|OK|ERROR
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_polled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = _ts()
class SearchSource(Base):
    __tablename__ = "search_sources"
    __table_args__ = (UniqueConstraint("search_id", "source_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    search_id: Mapped[str] = mapped_column(ForeignKey("search_configs.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"), index=True)
class IngestionEvent(Base):
    __tablename__ = "ingestion_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    source_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    channel: Mapped[str] = mapped_column(String(20))  # rss|jsonfeed|telegram|manual
    status: Mapped[str] = mapped_column(String(20))  # ok|duplicate|error|skipped
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = _ts()
class ListingImage(Base):
    __tablename__ = "listing_images"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    url: Mapped[str] = mapped_column(String(1000))
class ListingDeduplication(Base):
    __tablename__ = "listing_deduplication"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    search_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(20))  # exact | near
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = _ts()
class ListingScore(Base):
    __tablename__ = "listing_scores"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = _ts()
class UserListingAction(Base):
    __tablename__ = "user_listing_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[dt.datetime] = _ts()
class AiEmbedding(Base):
    __tablename__ = "ai_embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    memory_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    embedding: Mapped[list] = mapped_column(JSON)  # pgvector column `vec` is added by the optional revision
    created_at: Mapped[dt.datetime] = _ts()
class AgentJob(Base):
    __tablename__ = "agent_jobs"
    __table_args__ = (UniqueConstraint("dedupe_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending|running|done|failed|dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4)
    run_after: Mapped[dt.datetime] = _ts()
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[dt.datetime] = _ts()
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class AgentEvent(Base):
    __tablename__ = "agent_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    agent: Mapped[str] = mapped_column(String(30), index=True)
    event: Mapped[str] = mapped_column(String(30))  # started|completed|failed
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[dt.datetime] = _ts()
class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid(unique=True)
    in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    email: Mapped[bool] = mapped_column(Boolean, default=False)
    min_score: Mapped[int] = mapped_column(Integer, default=60)
class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(String(500), nullable=True)
    listing_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = _ts()
class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    provider: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="disconnected")
    created_at: Mapped[dt.datetime] = _ts()
class IntegrationSession(Base):
    __tablename__ = "integration_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id"), index=True)
    state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[dt.datetime] = _ts()
class WhatsappConnection(Base):
    __tablename__ = "whatsapp_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid(unique=True)
    number: Mapped[str] = mapped_column(String(20))
    consent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[dt.datetime] = _ts()
class AdminAction(Base):
    __tablename__ = "admin_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    admin_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = _ts()
