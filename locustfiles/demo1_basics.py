"""Demo 1 — Locust 入門：User / @task / wait_time / Web UI.

目的
    學會 Locust 三個核心概念，拿到第一份 p50/p95 報表。
    - User：一個虛擬使用者 = 一個 greenlet，獨立執行自己的任務迴圈
    - @task(weight)：任務與權重，read_posts(3) : read_users(1) = 75% : 25%
    - wait_time：每個任務之間的思考時間（真人不會連發請求）

跑法
    # 1. 起靶機（壓測一律關 access log、固定 1 worker）
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log

    # 2a. Web UI 模式（教學首選，開 http://localhost:8089）
    uv run locust -f locustfiles/demo1_basics.py

    # 2b. Headless 模式（之後自動化用）
    uv run locust -f locustfiles/demo1_basics.py --headless -u 50 -r 10 -t 60s

觀察
    - Web UI 的 Charts 分頁：RPS 與 p50/p95 曲線
    - 10 → 50 → 100 users 各跑一輪，記錄 p50 / p95 / RPS / error rate
    - 思考：有 wait_time(1,3) 時，100 users 的理論 RPS 上限是多少？
      （答案：100 users ÷ 平均 2s wait ≈ 50 RPS —— RPS 不是 users 數！）
"""

from locust import HttpUser, between, task


class SocialBrowser(HttpUser):
    host = "http://127.0.0.1:8000"
    wait_time = between(1, 3)

    @task(3)
    def read_posts(self) -> None:
        self.client.get("/async/posts")

    @task(1)
    def read_users(self) -> None:
        self.client.get("/async/users")
