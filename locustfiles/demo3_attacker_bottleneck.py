"""Demo 3 — 攻擊機瓶頸：HttpUser vs FastHttpUser.

目的
    Roadmap 的進階考點：「打超大流量時，攻擊機自己會先卡住」。
    在做任何靶機實驗之前，必須先確認攻擊機不是瓶頸 ——
    否則所有數據都是在測量 Locust，不是在測量靶機。

    - HttpUser：基於 requests（同步），每個請求都是純 Python 開銷
    - FastHttpUser：基於 geventhttpclient，C 實作 + gevent，3~5 倍吞吐

跑法（同樣參數打 /healthz，比較兩種武器）
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log

    # 第一輪：舊武器
    uv run locust -f locustfiles/demo3_attacker_bottleneck.py SlowAttacker --headless -u 500 -r 100 -t 30s

    # 第二輪：新武器（同參數）
    uv run locust -f locustfiles/demo3_attacker_bottleneck.py FastAttacker --headless -u 500 -r 100 -t 30s

    # 第三輪：真正的解法 —— 多 process（前菜：階段三的分散式 Locust）
    uv run locust -f locustfiles/demo3_attacker_bottleneck.py FastAttacker --processes 4 --headless -u 500 -r 100 -t 30s

觀察（重點：同時監控攻擊方！）
    另開 terminal 跑：
        top -stats pid,command,cpu -pid $(pgrep -f 'locust' | head -1)
    - SlowAttacker：locust process CPU 鎖死 100%（單核），RPS 上不去
      → 此時靶機 uvicorn 可能還很閒 —— 數據是假的，瓶頸在攻擊機
    - FastAttacker：同樣 500 users，RPS 明顯翻倍以上
    - --processes 4：再翻 —— 但接著瓶頸換人（靶機？網路？）

要能回答
    - 為什麼壓測報告一定要附「攻擊機資源使用率」？
    - Python GIL 在這裡扮演什麼角色？
    - 單機 --processes 與 K8s Master-Worker 分散式的差別是什麼？
"""

from locust import FastHttpUser, HttpUser, constant, task

HOST = "http://127.0.0.1:8000"


class SlowAttacker(HttpUser):
    """requests-based：每秒幾百 RPS 就會吃滿一顆 CPU。"""

    host = HOST
    wait_time = constant(0)

    @task
    def healthz(self) -> None:
        self.client.get("/healthz")


class FastAttacker(FastHttpUser):
    """geventhttpclient-based：同樣 users 數，RPS 翻數倍。"""

    host = HOST
    wait_time = constant(0)

    @task
    def healthz(self) -> None:
        self.client.get("/healthz")
