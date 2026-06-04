"""Demo 2 — 實驗 A/B/C：親眼看 event loop 被卡死.

目的
    Roadmap 階段 1-2 的三組對照實驗，用同樣的 20 users 打三個端點，
    體感 blocking / async / CPU bound 的天壤之別。

    | 實驗 | User class     | 端點                          | 預期                            |
    | ---- | -------------- | ----------------------------- | ------------------------------- |
    | B    | AsyncSleepUser | /experiments/async-sleep?seconds=1 | RPS ≈ 20，p95 ≈ 1s（正常）  |
    | A    | SyncSleepUser  | /experiments/sync-sleep?seconds=1  | RPS ≈ 1！p95 暴漲到數十秒   |
    | C    | CpuUser        | /experiments/cpu?n=30              | RPS ≈ 1/0.1s ≈ 10，全部排隊 |

跑法（一次跑一個 class，class 名接在 -f 後面）
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log

    uv run locust -f locustfiles/demo2_event_loop.py AsyncSleepUser --headless -u 20 -r 20 -t 30s
    uv run locust -f locustfiles/demo2_event_loop.py SyncSleepUser  --headless -u 20 -r 20 -t 30s
    uv run locust -f locustfiles/demo2_event_loop.py CpuUser        --headless -u 20 -r 20 -t 30s

殺手級示範（mentor 震撼教育）
    跑 SyncSleepUser 期間，開另一個 terminal：
        curl -m 5 http://127.0.0.1:8000/healthz
    → 連 health check 都 timeout！一個 time.sleep 就讓「整個服務」凍結。
    想像這是 production，K8s liveness probe 失敗 → Pod 被重啟 → 雪崩。

要能回答
    - 為什麼實驗 A 的 RPS 是 1，而不是 20？
    - 實驗 C 宣告成 async def 了，為什麼還是卡？
    - 哪些常見函式庫會像實驗 A 一樣偷偷 block？（requests、psycopg2、time.sleep...）
"""

from locust import HttpUser, constant, task

HOST = "http://127.0.0.1:8000"


class AsyncSleepUser(HttpUser):
    """實驗 B：await asyncio.sleep —— event loop 正常切換。"""

    host = HOST
    wait_time = constant(0)

    @task
    def async_sleep(self) -> None:
        self.client.get("/experiments/async-sleep?seconds=1")


class SyncSleepUser(HttpUser):
    """實驗 A：time.sleep 卡死整個 event loop，全服務凍結。"""

    host = HOST
    wait_time = constant(0)

    @task
    def sync_sleep(self) -> None:
        self.client.get("/experiments/sync-sleep?seconds=1")


class CpuUser(HttpUser):
    """實驗 C：CPU bound —— async 宣告也救不了，照樣串行。"""

    host = HOST
    wait_time = constant(0)

    @task
    def cpu(self) -> None:
        self.client.get("/experiments/cpu?n=30")
