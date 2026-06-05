"""Demo 5 — Pool Starvation：connection pool 才是 p95 的主宰.

目的
    Roadmap 筆記範例的重現：「pool starvation dominates latency」。
    固定攻擊參數，只改靶機的 DB_POOL_SIZE，掃出 p95 對 pool 大小的曲線。
    這個 demo 回答「為何 connection pool 重要」與「為何 DB 才是真 bottleneck」。

跑法（容器模式；攻擊參數固定，每輪重置 + 換 pool 大小）
    # 每輪：重置 DB（鐵則 3）→ 換 pool 重啟 → 同一個攻擊 → 驗證 → 記錄。
    # DB_POOL_SIZE 必須 export：後面的 compose run 也會重新解析設定，
    # 沒 export 的話它會以預設 pool=5 把 app 重建回去（真實踩過的坑 ——
    # 症狀是「pool 怎麼掃數據都一樣」）。
    docker compose down
    export DB_POOL_SIZE=10
    docker compose up -d --build --wait
    docker compose run --rm locust -f /mnt/locust/demo5_pool_starvation.py \
        --host http://app:8000 --headless -u 200 -r 100 -t 60s
    docker inspect k8s-app-1 --format '{{.Config.Env}}' | tr ' ' '\\n' | grep DB_POOL  # 驗證旋鈕

    # 下一輪換 export DB_POOL_SIZE=20 / 50 / 100，攻擊參數不動

跑法（本機模式）
    DB_POOL_SIZE=10  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
    uv run locust -f locustfiles/demo5_pool_starvation.py --headless -u 200 -r 100 -t 60s
    # DB_POOL_SIZE=20 / 50 / 100 同上各跑一輪

預期（delay_ms=50，200 併發；理論 RPS 上限 = pool / 0.05s）
    | DB_POOL_SIZE | RPS 上限 | 預期 p95（≈ users / RPS） |
    | ------------ | -------- | ------------------------- |
    | 10           | 200      | ~1000ms（排隊嚴重）       |
    | 20           | 400      | ~500ms                    |
    | 50           | 1000     | ~200ms                    |
    | 100          | 2000     | ~100ms（幾乎不排隊）      |

    注意：這是押注值，實測會系統性更高（pool=100 實測 p95=420ms）——
    connection 實佔 ~60ms 而非 50ms（fetch + ORM 序列化），且 pool≥50 後
    瓶頸轉移到 event loop CPU。對答案與完整數據見 README「已驗證數據」。

    把四輪的 p95 畫成曲線 —— 這張圖就是教材。

進一步思考（senior thinking）
    - pool 開越大越好嗎？PG 每條 connection 都是一個 process，
      max_connections 撞到會怎樣？（我們 compose 已調到 200 ——
      pool=100 時 sync + async 兩組剛好用滿；PG 預設只有 100）
    - 如果 DB 在 delay 期間其實在做真查詢（吃 CPU），開 100 條同時打，
      DB 端會發生什麼事？（劇透：throughput 反而下降 —— 之後階段四用 metrics 驗證）

Problem-Driven 筆記模板（跑完照填）
    Problem:    p95 在 200 併發時 ___ms，太慢
    Hypothesis: DB connection pool 耗盡，請求在 pool 前排隊
    Experiment: DB_POOL_SIZE 10 → 100，同攻擊參數各跑 60s
    Result:     p95 ___ms → ___ms
    Lesson:     ___
"""

from locust import FastHttpUser, constant, task

DELAY_MS = 50


class PoolProbeUser(FastHttpUser):
    host = "http://127.0.0.1:8000"
    wait_time = constant(0)

    @task
    def posts_async(self) -> None:
        self.client.get(f"/async/posts?delay_ms={DELAY_MS}", name="/async/posts")
