"""壓測靶機（Target）— Mini Social Platform.

大流量壓測訓練的靶機服務：
階段一在本地用 Locust 打它，階段二容器化，階段三上 K8s + HPA。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.db import POOL_SIZE, AsyncSession, async_engine, sync_engine
from app.routers import experiments, social


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 預熱兩個 pool：一次握住 POOL_SIZE 條連線強制建立，再放回 pool。
    # 維持舊設計 open(wait=True) 的語義 —— 壓測一開始 pool 就是滿的，
    # 第一波請求不必付建立連線的成本，數據才乾淨。DB 沒起來則直接 fail fast。
    sync_conns = [sync_engine.connect() for _ in range(POOL_SIZE)]
    for c in sync_conns:
        c.close()
    async_conns = [await async_engine.connect() for _ in range(POOL_SIZE)]
    for c in async_conns:
        await c.close()
    yield
    await async_engine.dispose()
    sync_engine.dispose()


app = FastAPI(
    title="Mini Social Platform — 壓測靶機",
    description="Locust x Async x K8s 訓練用靶機。/docs 看完整端點清單。",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(social.sync_router)
app.include_router(social.async_router)
app.include_router(experiments.router)


@app.get("/", tags=["ops"])
async def root() -> dict:
    return {"status": "ok"}


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    """K8s liveness probe 用。不碰 DB，永遠要快。"""
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz() -> dict:
    """K8s readiness probe 用：真的打一次 DB，確認服務「可以收流量」。

    liveness vs readiness 的差異是 K8s 章節的重要考點。
    """
    async with AsyncSession() as session:
        await session.execute(select(1))
    return {"status": "ready"}
