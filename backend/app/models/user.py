"""
Authentication & Account Lifecycle ORM Models.

Tables added non-destructively alongside the existing 16 operational tables:
- users: Role-based platform accounts (admin | hospital | warehouse | delivery)
- refresh_tokens: Hashed refresh sessions supporting rotation, revocation & logout
- password_reset_tokens: Single-use, short-lived hashed password recovery tokens
- email_verification_tokens: Single-use hashed account verification tokens
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, utcnow


class User(Base, TimestampMixin):
    """Authenticated platform user bound to a role and optional organization."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="hospital"
    )  # admin | hospital | warehouse | delivery
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="pending"
    )  # pending | approved | rejected
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    associated_hospital_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), index=True, nullable=True
    )
    associated_warehouse_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="SET NULL"), index=True, nullable=True
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    hospital = relationship("Hospital")
    warehouse = relationship("Warehouse")
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """Persisted hashed refresh token supporting rotation and revocation."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user = relationship("User", back_populates="refresh_tokens")


class PasswordResetToken(Base):
    """Short-lived, single-use hashed password recovery token."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user = relationship("User")


class EmailVerificationToken(Base):
    """Single-use hashed account verification token."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user = relationship("User")
