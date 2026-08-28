from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


def new_uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    score: Mapped[int] = mapped_column(Integer, default=0)
    has_private_chat: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sessions: Mapped[list["GameSession"]] = relationship(back_populates="user")


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_group_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameSession(Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        Index("ix_game_sessions_chat_status", "chat_id", "status"),
        Index("ix_game_sessions_user_status", "user_id", "status"),
        Index(
            "uq_game_sessions_one_active_chat",
            "chat_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    mode: Mapped[str] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    user: Mapped[User] = relationship(back_populates="sessions")
    rounds: Mapped[list["Round"]] = relationship(back_populates="session")


class WhoCloserParticipant(Base):
    __tablename__ = "who_closer_participants"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_who_closer_participant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    added_time: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhoCloserAnswer(Base):
    __tablename__ = "who_closer_answers"
    __table_args__ = (
        UniqueConstraint("round_id", "user_id", name="uq_who_closer_answer_user"),
        UniqueConstraint("round_id", "price", name="uq_who_closer_answer_price"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Round(Base):
    __tablename__ = "rounds"
    __table_args__ = (
        Index(
            "ix_rounds_session_resolved_created",
            "session_id",
            "resolved_at",
            "created_at",
        ),
        Index(
            "uq_rounds_one_pending_session",
            "session_id",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
            sqlite_where=text("resolved_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64))
    source_listing_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(Text)
    source_description: Mapped[str] = mapped_column(Text)
    translated_title: Mapped[str] = mapped_column(Text)
    translated_description: Mapped[str] = mapped_column(Text)
    source_price: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    source_currency: Mapped[str] = mapped_column(String(3))
    conversion_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    displayed_price: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    displayed_currency: Mapped[str] = mapped_column(String(3))
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    card_message_id: Mapped[int | None] = mapped_column(Integer)
    answer: Mapped[str | None] = mapped_column(Text)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    provider_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rate_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session: Mapped[GameSession] = relationship(back_populates="rounds")


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_currency: Mapped[str] = mapped_column(String(3))
    target_currency: Mapped[str] = mapped_column(String(3), unique=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    provider_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
