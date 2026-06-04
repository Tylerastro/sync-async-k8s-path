"""Social 端點 —— sync / async 對照，全部集中在這一支檔案，用 tags 區分。

兩個 router 用 prefix 切開（Swagger UI 會自動依 tag 分成兩組）：
    /sync/*   → `def` 端點，跑在 threadpool + sync engine
    /async/*  → `async def` 端點，跑在 event loop + async engine

同樣的資源（users / posts / message）各做一份 sync、一份 async，
壓測時 /sync/posts vs /async/posts 直接對照 —— 這是階段一的核心對照組。

delay_ms：用 func.pg_sleep 模擬慢查詢，佔住 connection，重現 pool starvation。
"""

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.db import AsyncSession, SyncSession
from app.models import Message, Post, User
from app.schemas import MessageIn, MessageOut
from app.schemas import Post as PostSchema
from app.schemas import User as UserSchema

sync_router = APIRouter(prefix="/sync", tags=["sync"])
async_router = APIRouter(prefix="/async", tags=["async"])

USERS_STMT = select(User).order_by(User.id)
POSTS_STMT = select(Post).order_by(Post.id)
DelayMs = Query(
    default=100, ge=0, le=5000, description="用 pg_sleep 模擬慢查詢（毫秒）"
)


# ───────────────── sync：def → threadpool（預設 40 條）+ sync engine ─────────────────
# 瓶頸有兩層，壓測時要分清楚是誰先死：
#   1. threadpool 40 條 thread
#   2. sync engine pool 只有 DB_POOL_SIZE 條 connection


@sync_router.get("/users", response_model=list[UserSchema])
def sync_users() -> list[User]:
    with SyncSession() as session:
        return session.execute(USERS_STMT).scalars().all()


@sync_router.get("/posts", response_model=list[PostSchema])
def sync_posts(delay_ms: int = DelayMs) -> list[Post]:
    with SyncSession() as session:
        if delay_ms:
            session.execute(select(func.pg_sleep(delay_ms / 1000)))
        return session.execute(POSTS_STMT).scalars().all()


@sync_router.post("/message", response_model=MessageOut, status_code=201)
def sync_message(message: MessageIn) -> MessageOut:
    with SyncSession() as session:
        msg = Message(**message.model_dump())
        session.add(msg)
        session.commit()
        return MessageOut(id=msg.id, **message.model_dump())


# ──────────────── async：async def → event loop + async engine ────────────────
# await DB 期間 event loop 切去服務其他請求，不佔 thread。
# 瓶頸只有 async engine pool —— 但 ORM 物件序列化是 CPU 工作，擠在 event loop 上。


@async_router.get("/users", response_model=list[UserSchema])
async def async_users() -> list[User]:
    async with AsyncSession() as session:
        result = await session.execute(USERS_STMT)
        return result.scalars().all()


@async_router.get("/posts", response_model=list[PostSchema])
async def async_posts(delay_ms: int = DelayMs) -> list[Post]:
    async with AsyncSession() as session:
        if delay_ms:
            await session.execute(select(func.pg_sleep(delay_ms / 1000)))
        result = await session.execute(POSTS_STMT)
        return result.scalars().all()


@async_router.post("/message", response_model=MessageOut, status_code=201)
async def async_message(message: MessageIn) -> MessageOut:
    async with AsyncSession() as session:
        msg = Message(**message.model_dump())
        session.add(msg)
        await session.commit()
        return MessageOut(id=msg.id, **message.model_dump())
