# 壓測靶機 — Mini Social Platform

大流量壓測訓練（Locust x Async x K8s）的靶機（Target）服務。FastAPI + SQLAlchemy ORM + 真 PostgreSQL。

> 訓練主軸：**看到 metrics → 提出假設 → 設計實驗 → 驗證**
> 路線：單機 → 容器 → 叢集 → 觀測調校

## 快速開始

```bash
docker compose up -d --wait   # 起 PostgreSQL（host port 5433），自動建表 + seed
uv sync
uv run main.py                # 開發模式（hot-reload），http://127.0.0.1:8000
```

壓測時改用（關掉 reload、固定 1 worker，先看清單一 event loop 的行為）：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

互動式 API 文件：http://127.0.0.1:8000/docs

> DB 刻意不掛 volume：`docker compose down && docker compose up -d --wait`
> 即重置回同一份 seed（50 users / 200 posts），每輪實驗數據才有可比性。

## 環境變數（實驗旋鈕）

| 變數 | 預設 | 用途 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://app:app@localhost:5433/social` | PG 連線字串（會自動補上 `+psycopg` driver） |
| `DB_POOL_SIZE` | `5` | 兩個 engine 的 `pool_size`（配 `max_overflow=0` → 固定大小）——「pool starvation」實驗的主旋鈕 |

## 兩個 SQLAlchemy Engine（核心對照組）

兩個 engine **都用 psycopg3 driver**（`postgresql+psycopg://`）+ 同一種 SQLAlchemy QueuePool：
同 driver、同 pool 實作，唯一變因是 `create_engine`（sync）vs `create_async_engine`（async），
差異才能歸因給併發模型，而不是 driver 效能差異。

| | sync engine | async engine |
| --- | --- | --- |
| 端點宣告 | `def` → FastAPI 丟進 threadpool（預設 40 條） | `async def` → 跑在 event loop |
| 等待 DB 時 | 佔住一條 thread | event loop 切去服務其他請求 |
| 瓶頸層次 | threadpool 40 條 **和** pool 連線數 | 只有 pool 連線數 |
| ORM 序列化 | 分散在多條 thread | **全擠在 event loop 上**（見下方實驗 Lesson 3） |

## 端點總覽

### Social（業務端點，真 DB I/O）

每種資源各一份 sync / async，用 prefix 對稱切開，壓測時同名直接對照。
Swagger UI（`/docs`）會依 tag 分成 **sync** / **async** 兩組。

| sync（`def` + threadpool + sync engine） | async（`async def` + event loop + async engine） | 說明 |
| --- | --- | --- |
| `GET /sync/users` | `GET /async/users` | 使用者列表 |
| `GET /sync/posts` | `GET /async/posts` | 貼文列表 |
| `POST /sync/message` | `POST /async/message` | 寫入 messages 表（觀察讀寫不對稱） |

`/{sync,async}/posts` 都吃 `?delay_ms=`（0–5000）：用 `func.pg_sleep` 模擬慢查詢，
查詢期間 connection 被佔住 —— 重現 pool starvation 的旋鈕。

### Experiments（純 event loop 實驗，不碰 DB）

| 實驗 | 端點 | 觀察重點 |
| --- | --- | --- |
| A | `GET /experiments/sync-sleep?seconds=1` | blocking sleep —— 整個 event loop 卡死 |
| B | `GET /experiments/async-sleep?seconds=1` | async sleep —— event loop 切去服務其他請求 |
| C | `GET /experiments/cpu?n=30` | CPU bound —— async 也救不了 |

### Ops

| 端點 | 說明 |
| --- | --- |
| `GET /healthz` | liveness：不碰 DB，永遠要快 |
| `GET /readyz` | readiness：真打一次 DB，確認可收流量 |

## 已驗證的實驗數據（2026-06-04，SQLAlchemy ORM stack）

```text
Problem:    sync vs async 到底差在哪？什麼時候差異會現形？
Hypothesis: 併發 > threadpool(40) 且 pool 夠大時，sync 因排隊 p95 飆高
Experiment: 100 併發 x delay_ms=100

  pool=10:  async wall=1.28s (p95=1264ms) ≈ sync wall=1.28s (p95=1271ms)
                                               ← pool 是共同瓶頸，async 不是魔法
  pool=100: async wall=0.23s (p95=231ms)
            sync  wall=0.42s (p95=398ms)        ← threadpool 40 條成為瓶頸

Lesson 1:   瓶頸在誰身上，誰就決定 p95 —— pool 小時 sync/async 沒差
Lesson 2:   攻擊機也會是瓶頸：xargs+curl 起 100 個 process 的 fork 開銷
            就吃掉 0.3s，差異完全被淹沒（→ Locust 要用 FastHttpUser）
Lesson 3:   ORM 不是免費的。換 SQLAlchemy 後 async 的絕對延遲變高、
            領先幅度從 ~3x 縮到 ~1.5x —— 因為 200 筆 row → ORM 物件的
            序列化是 CPU 工作，在 async 全擠在「單一 event loop」上無法重疊；
            sync 版則分散在 threadpool。抽象層的成本，async 要自己扛。
```

> raw psycopg 版的對照數據（async 931 RPS / sync 372 RPS，差 ~2.5x）保留在 git 歷史，
> 可跟現在的 ORM 版對比，量化「ORM 抽象層的代價」。

注意：PG 預設 `max_connections=100`，兩個 engine 各開 100 會撞死，
compose 已調到 500（production 不會這樣做，這本身是考點）。

## 專案結構

```
compose.yaml             # PostgreSQL 17（host port 5433）
db/init.sql              # schema + seed（50 users / 200 posts）
app/
├── main.py              # FastAPI app、lifespan（預熱 pool + dispose）、healthz/readyz
├── db.py                # sync + async 兩個 SQLAlchemy engine（DB_POOL_SIZE 控制）
├── models.py            # SQLAlchemy ORM models（mapping init.sql 既有的表）
├── schemas.py           # Pydantic models（API 契約，response 開 from_attributes）
└── routers/
    ├── social.py        # /sync/* 與 /async/* 兩個 router（users/posts/message）
    └── experiments.py   # 實驗 A / B / C（不碰 DB）
main.py                  # 開發用入口
```

## Locust 壓測 Demo

六支教學腳本在 [`locustfiles/`](locustfiles/README.md)，已規劃好 demo 順序
（工具 → event loop → 攻擊機瓶頸 → sync/async 對照 → pool starvation → 階梯大流量），
每支 docstring 都有完整 runbook 與預期數字。已驗證的 Locust 數據：

```text
demo4（100 users, delay_ms=100, pool=100, SQLAlchemy ORM）:
  async  512 RPS  p50=200ms   ← ORM 序列化擠在 event loop，比 raw 的 931 低
  sync   335 RPS  p50=290ms   ← threadpool 40 條成為瓶頸

demo3（300 users 打 /healthz）:
  HttpUser      5,921 RPS    ← 攻擊機自己是瓶頸
  FastHttpUser 24,762 RPS    ← 同參數，4.2 倍
```

## 下一步（對齊 Roadmap）

- [ ] 跑完 demo1~6 並用 Problem-Driven 格式記錄（demo5 的 p95 曲線、demo6 的崩潰點）
- [ ] 階段二：Dockerfile（multi-stage，靶機 + Locust 都容器化）+ 本地 K8s 部署
