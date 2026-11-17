"""Agent tables (v3.3). Additive: two new tables, both with a user_id FK so the existing generic
purge (DELETE /api/me) and export (/api/me/export/full) cover them automatically."""
import datetime as dt
from sqlalchemy import String, Integer, JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import _id
from .models2 import _ts, _uid


class AgentMemory(Base):
    """Long-term memory the agent keeps about the user: facts, preferences, goals, conversation summaries."""
    __tablename__ = "agent_memory"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    kind: Mapped[str] = mapped_column(String(12), default="fact")  # fact | preference | goal | summary
    text: Mapped[str] = mapped_column(String(500))
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = _ts()


class AgentMessage(Base):
    """Short-term conversation history (rolled up into a 'summary' memory when it grows)."""
    __tablename__ = "agent_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = _uid()
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    actions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = _ts()


# v3.16 performance indexes (mirrored by migration a9b8c7d6e5f4)
from sqlalchemy import Index
Index("ix_agent_memory_user_created", AgentMemory.user_id, AgentMemory.created_at)
Index("ix_agent_messages_user_created", AgentMessage.user_id, AgentMessage.created_at)
