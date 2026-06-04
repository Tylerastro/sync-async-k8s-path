"""SQLAlchemy ORM models —— 對應 db/init.sql 既有的表。

表與 seed 由 init.sql 在 DB 啟動時建立，這裡只負責 mapping，
不呼叫 metadata.create_all（資料已經在了）。

教學點：ORM 比 raw SQL 多一層物件序列化開銷（每筆 row → Python 物件）。
壓測時 /posts 回 200 筆，這個開銷在高 RPS 下會出現在 CPU profile 裡 ——
之後可以用 raw Core query 對比，這也是 /posts/optimized 的調校方向之一。
"""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    display_name: Mapped[str]


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str]
    likes: Mapped[int]


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
