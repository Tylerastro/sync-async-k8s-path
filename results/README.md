# results/ — 壓測原始數據（2026-06-05，容器模式）

README 與 index.html 引用的每個數字都出自這裡 —— 教材數據要可追溯。

## 檔名規則

```
demo5_pool{N}_locust.txt          # Locust 終局報表（含 percentile 表）
demo5_pool{N}_stats.csv           # 同上的 CSV 版
demo5_pool{N}_stats_history.csv   # 每 10s 的時間序列
demo5_pool{N}_dockerstats.txt     # 攻擊進行到 ~35s 時兩側容器的 CPU/MEM（鐵則 1）
demo6_locust.txt                  # 階梯全程 console 輸出（每 10s 統計 = 逐階數據來源）
demo6_dockerstats.txt             # 每 ~20s 採樣的兩側資源時間線
demo6_app_state.txt               # 跑完後靶機容器狀態（OOMKilled? Restarts?）
demo6_app_logs.txt                # 靶機日誌（QueuePool timeout 的證據在這）
```

## 實驗條件

- demo5：200 users / delay_ms=50 / FastHttpUser / 60s，每輪重置 DB、只動 `DB_POOL_SIZE`
- demo6：pool=100 / `--processes 4` / StepLoadShape 10→100→1000→5000（每階 2 分鐘）
- 環境：OrbStack 10 vCPU，cpuset 隔離（db=0,1 / 靶機=2,3 / 攻擊機=4-7）

## 特別保留

- `demo5_pool5_ACCIDENTAL_locust.txt` — 「旋鈕沒接上」事故的證物：
  DB_POOL_SIZE 沒 export，四輪全打在預設 pool=5 上。
  留著它，因為「假數據長什麼樣」本身就是教材（見 locustfiles/README 坑點）。
