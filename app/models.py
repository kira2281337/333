import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, or_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")

    links: Mapped[list["Link"]] = relationship(back_populates="user")


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_url: Mapped[str] = mapped_column(Text)
    code: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, index=True, default=uuid.uuid4)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicks: Mapped[int] = mapped_column(default=0, server_default="0")
    max_clicks: Mapped[int | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="links")

    @classmethod
    def active_conditions(cls, now: datetime | None = None) -> tuple:
        """Единственное место, где определено, что такое «активная ссылка».

        Активная = не удалена, не истекла по времени, лимит кликов не исчерпан.
        Используется и при подсчёте лимита, и при редиректе, и при поиске дубликата.
        """
        now = now or utcnow()
        return (
            cls.deleted_at.is_(None),
            or_(cls.expires_at.is_(None), cls.expires_at > now),
            or_(cls.max_clicks.is_(None), cls.clicks < cls.max_clicks),
        )
