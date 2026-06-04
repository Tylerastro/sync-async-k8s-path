# Locust Demo 腳本 — 教學順序

> 順序設計邏輯：**先學工具（1）→ 先懂 event loop（2）→ 先排除攻擊機瓶頸（3）
> → 才做靶機實驗（4、5）→ 最後整合大流量（6）**。
> 跳過 3 直接做 4，你測到的會是 Locust 的極限，不是靶機的。

| # | 腳本 | 課題 | 戲劇點 |
| --- | --- | --- | --- |
| 1 | `demo1_basics.py` | `User` / `@task` / `wait_time` / Web UI | 第一份 p50/p95 報表；RPS ≠ users 數 |
| 2 | `demo2_event_loop.py` | 實驗 A/B/C：event loop 卡死實況 | 一個 `time.sleep` 凍結全服務，healthz 也死 |
| 3 | `demo3_attacker_bottleneck.py` | `HttpUser` vs `FastHttpUser` | 攻擊機 CPU 先鎖死 100%；換武器 RPS 翻倍 |
| 4 | `demo4_sync_vs_async_db.py` | sync vs async 打真 PG（核心對照） | 同 100 併發，p95 差 3 倍 |
| 5 | `demo5_pool_starvation.py` | `DB_POOL_SIZE` 10→100 掃描 | pool 主宰 p95；async 不是魔法 |
| 6 | `demo6_step_load_social.py` | 階梯 10→100→1000→5000 混合流量 | 找到崩潰點 = 階段三 HPA 的 baseline |

每支腳本的 docstring 都有完整 runbook：跑法指令、預期數字、觀察重點、要能回答的問題。

## 共通前置

```bash
docker compose up -d --wait                  # DB（host port 5433）
ulimit -n 10240                              # demo6 必須；其他 demo 建議一起開

# 靶機：壓測一律關 access log、預設 1 worker
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log

# demo4 之後要開大 pool：
DB_POOL_SIZE=100 uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

## 鐵則

1. **同時監控攻擊方與防守方**（CPU / MEM）——分不清瓶頸在誰身上的數據沒有意義
2. **一次只改一個變因**：users 數、pool 大小、sync/async，不要同時動
3. **每輪重置 DB**（`docker compose down && docker compose up -d --wait`），seed 一致數據才可比
4. demo 結果一律用 Problem-Driven 格式記錄：

```text
Problem:    （觀察到什麼異常／想驗證什麼）
Hypothesis: （你認為的原因）
Experiment: （改了什麼、攻擊參數）
Result:     （p50 / p95 / RPS / error rate / 兩側 CPU·MEM）
Lesson:     （一句話，能教給別人的那種）
```
