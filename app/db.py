"""兩個 SQLAlchemy engine —— 實驗的核心對照組。

刻意兩個 engine 都用 psycopg3（`postgresql+psycopg://`）：
SQLAlchemy 的 psycopg dialect 同時支援 sync 與 async，
所以同 driver、同 pool 實作（SQLAlchemy QueuePool），
唯一變因就是 `create_engine`（sync）vs `create_async_engine`（async），
壓測差異才能歸因給併發模型，而不是 driver 效能差異。

pool 大小用 DB_POOL_SIZE 控制，搭配 max_overflow=0 → 固定大小（等同舊設計的 min=max）。
這就是 roadmap 裡「pool starvation dominates latency」實驗的旋鈕：
壓測時把它從 10 調到 100，觀察 p95 的變化。

pool_timeout 預設 30s：pool 耗盡時請求會等 30s 才丟 TimeoutError ——
demo6 看到的某些 error 就是它。
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

BASE_URL = os.getenv("DATABASE_URL", "postgresql://app:app@localhost:5433/social")
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))

# psycopg3 driver 同時給 sync / async engine 用 —— 維持「同 driver」的控制變因
DB_URL = BASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# sync engine：給 `def` 端點用（FastAPI 丟進 threadpool 執行）
sync_engine = create_engine(
    DB_URL,
    pool_size=POOL_SIZE,
    max_overflow=0,  # 固定大小：超過 pool_size 的請求排隊，不臨時開新連線
)

# async engine：給 `async def` 端點用（跑在 event loop 上）
async_engine = create_async_engine(
    DB_URL,
    pool_size=POOL_SIZE,
    max_overflow=0,
)

# expire_on_commit=False：commit 後 ORM 物件屬性不過期，
# 才能在 session 關閉後（FastAPI 序列化 response 時）安全讀取，不觸發 lazy IO
SyncSession = sessionmaker(sync_engine, expire_on_commit=False)
AsyncSession = async_sessionmaker(async_engine, expire_on_commit=False)
