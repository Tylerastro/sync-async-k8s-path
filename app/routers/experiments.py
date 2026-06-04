"""刻意實驗端點 —— Roadmap 階段 1-2 的三組對照實驗。

| 實驗 | 端點                      | 觀察重點                       |
| ---- | ------------------------- | ------------------------------ |
| A    | /experiments/sync-sleep   | 整個 worker 卡死               |
| B    | /experiments/async-sleep  | event loop 切換出去做別的事    |
| C    | /experiments/cpu          | event loop 一樣被卡死          |

用 Locust 對三個端點各打一輪，記錄 p50 / p95 / throughput 的差異。
"""

import asyncio
import time

from fastapi import APIRouter, Query

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/sync-sleep")
async def sync_sleep(seconds: float = Query(default=1.0, ge=0, le=10)) -> dict:
    """實驗 A：在 async 端點裡呼叫 blocking 的 time.sleep。

    這是經典的 async 陷阱 —— event loop 被整個卡住，
    這 1 秒內「所有」其他請求都動不了。
    """
    time.sleep(seconds)
    return {"experiment": "A", "blocking": True, "slept": seconds}


@router.get("/async-sleep")
async def async_sleep(seconds: float = Query(default=1.0, ge=0, le=10)) -> dict:
    """實驗 B：await asyncio.sleep —— event loop 切出去服務其他請求。

    跟實驗 A 用同樣的併發數打，對比 RPS。
    """
    await asyncio.sleep(seconds)
    return {"experiment": "B", "blocking": False, "slept": seconds}


@router.get("/cpu")
async def cpu_bound(n: int = Query(default=30, ge=1, le=35)) -> dict:
    """實驗 C：CPU bound（遞迴費波那契）。

    就算宣告成 async，CPU 計算沒有 await 點，
    event loop 一樣被卡死 —— async 對 CPU bound 沒有幫助。
    n=30 約 0.1s、n=33 約 0.5s（依機器而定）。
    """
    started = time.perf_counter()
    result = _fib(n)
    elapsed = time.perf_counter() - started
    return {"experiment": "C", "n": n, "fib": result, "elapsed_seconds": round(elapsed, 4)}


def _fib(n: int) -> int:
    if n < 2:
        return n
    return _fib(n - 1) + _fib(n - 2)
