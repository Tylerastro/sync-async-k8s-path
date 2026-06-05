"""Demo 4 — 核心對照：sync vs async 打真 PostgreSQL.

目的
    本訓練計畫的核心實驗。前置（demo1~3）都是為了此刻：
    工具會用了、event loop 懂了、攻擊機不是瓶頸了 —— 現在打真 DB。

    Problem:    sync / async 到底差在哪？何時現形？
    Hypothesis: 併發 > threadpool(40) 且 pool 夠大時，
                sync 因 threadpool 排隊，p95 約為 async 的 3 倍
    （已用 curl 在 100 併發初驗過：async p95=119ms vs sync p95=342ms）

跑法（容器模式）
    # 靶機要開大 pool（讓 threadpool 成為 sync 的瓶頸，而不是 pool）
    DB_POOL_SIZE=100 docker compose up -d --build --wait

    # 兩輪同參數，只換 class
    docker compose run --rm locust -f /mnt/locust/demo4_sync_vs_async_db.py AsyncPostsUser \
        --host http://app:8000 --headless -u 100 -r 50 -t 60s
    docker compose run --rm locust -f /mnt/locust/demo4_sync_vs_async_db.py SyncPostsUser \
        --host http://app:8000 --headless -u 100 -r 50 -t 60s

跑法（本機模式）
    DB_POOL_SIZE=100 uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
    uv run locust -f locustfiles/demo4_sync_vs_async_db.py AsyncPostsUser --headless -u 100 -r 50 -t 60s
    uv run locust -f locustfiles/demo4_sync_vs_async_db.py SyncPostsUser  --headless -u 100 -r 50 -t 60s

預期（delay_ms=100，每個請求佔住 connection 100ms）
    | class          | 理論 RPS 上限            | 預期 p95   |
    | -------------- | ------------------------ | ---------- |
    | AsyncPostsUser | 100 conn / 0.1s = 1000   | ~120ms     |
    | SyncPostsUser  | 40 threads / 0.1s = 400  | ~300ms+    |

    接著把 -u 拉到 200、400，觀察 sync 的 p95 線性惡化、async 撐到 pool 滿才惡化。

要能回答
    - sync 版的 40 是哪來的？（AnyIO threadpool 預設容量 —— 可以調，但調大是對的嗎？）
    - 如果 DB_POOL_SIZE=10，這個實驗會看到什麼？（劇透：兩者一樣慢 —— 自己跑 demo5 驗證）
"""

from locust import FastHttpUser, constant, task

HOST = "http://127.0.0.1:8000"
DELAY_MS = 100


class AsyncPostsUser(FastHttpUser):
    """打 async 版：event loop + async pool。"""

    host = HOST
    wait_time = constant(0)

    @task
    def posts_async(self) -> None:
        self.client.get(f"/async/posts?delay_ms={DELAY_MS}", name="/async/posts")


class SyncPostsUser(FastHttpUser):
    """打 sync 版：threadpool + sync pool。"""

    host = HOST
    wait_time = constant(0)

    @task
    def posts_sync(self) -> None:
        self.client.get(f"/sync/posts?delay_ms={DELAY_MS}", name="/sync/posts")
