"""Demo 6 — 階梯式壓測：10 → 100 → 1000 → 5000 users 混合流量.

目的
    Roadmap 1-3 的終點：用「擬真的混合流量」做階梯式壓測，找到系統崩潰點。
    SocialUser 模擬真實使用者行為（讀寫不對稱）：
        滑 feed (10) : 看用戶 (3) : 發訊息 (1)
    LoadTestShape 自動控制階梯，不用手動調 users。

跑法（容器模式 —— 兩側容器的 fd 上限 nofile=10240 已在 compose 設好，免調 ulimit）
    DB_POOL_SIZE=100 docker compose up -d --build --wait

    # 階梯由 StepLoadShape 控制，不需要 -u/-r/-t；
    # 5000 users 必須上多 process（locust 容器有 4 顆核心 → --processes 4）
    docker compose run --rm locust -f /mnt/locust/demo6_step_load_social.py \
        --host http://app:8000 --processes 4 --headless

    # 想看圖表就用 Web UI 模式（教學示範建議）：
    # 先停掉預設的 locust 服務（讓出 8089），再帶 port 起一次性的 run
    docker compose stop locust
    docker compose run --rm --service-ports locust \
        -f /mnt/locust/demo6_step_load_social.py --host http://app:8000 --processes 4

跑法（本機模式）
    # macOS 預設 ulimit -n 只有 256，5000 連線直接撞「Too many open files」
    # （Roadmap 階段 4-2 的系統限制，現在就會遇到！）
    ulimit -n 10240

    DB_POOL_SIZE=100 uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
    uv run locust -f locustfiles/demo6_step_load_social.py --processes 4 --headless

每一階記錄（Roadmap 指定欄位）
    p50 / p95 / throughput / error rate / 靶機 CPU·MEM / 攻擊機 CPU·MEM

觀察重點
    - 哪一階開始 p95 飆升？哪一階開始出現 error？error 是什麼？
      （connection refused？timeout？pool timeout 30s？）
    - 崩潰點出現時，瓶頸是誰：threadpool？pool？PG？uvicorn 單 worker？ulimit？
    - 這裡找到的崩潰點，就是階段三 HPA 實驗的 baseline ——
      「單 Pod 撐到 N users」，之後驗證「3 Pods 是否撐到 3N」。

要能回答
    - 為什麼發訊息（寫入）的 p95 比讀 posts 高？
    - wait_time(1,3) 下，5000 users 的理論 RPS 是多少？（≈ 2500，不是 5000）
"""

import random

from locust import FastHttpUser, LoadTestShape, between, task


class SocialUser(FastHttpUser):
    """擬真使用者：滑 feed 為主、偶爾發訊息（讀寫 ≈ 13:1）。"""

    host = "http://127.0.0.1:8000"
    wait_time = between(1, 3)

    @task(10)
    def browse_feed(self) -> None:
        self.client.get("/async/posts")

    @task(3)
    def view_users(self) -> None:
        self.client.get("/async/users")

    @task(1)
    def send_message(self) -> None:
        self.client.post(
            "/async/message",
            json={
                "sender_id": random.randint(1, 50),
                "recipient_id": random.randint(1, 50),
                "content": "load test message",
            },
        )


class StepLoadShape(LoadTestShape):
    """階梯：每階 2 分鐘，10 → 100 → 1000 → 5000。

    跑完最後一階回傳 None，Locust 自動結束並印總結報表。
    """

    stages = [
        {"end_time": 120, "users": 10, "spawn_rate": 10},
        {"end_time": 240, "users": 100, "spawn_rate": 50},
        {"end_time": 360, "users": 1000, "spawn_rate": 100},
        {"end_time": 480, "users": 5000, "spawn_rate": 200},
    ]

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["end_time"]:
                return (stage["users"], stage["spawn_rate"])
        return None
