# 階段二（下）：本地 K8s 部署 Runbook

> 環境：OrbStack 內建 K8s（context: orbstack）
> 目標：把靶機 + DB 部上本地 K8s，用 host 上的 Locust 打它
> 前置：compose 模式（階段二上）已完成、demo1~6 的 baseline 數據已記錄

---

## 一、前置條件確認

```bash
# 確認 OrbStack K8s 已啟動，且 context 是 orbstack
kubectl config current-context
# 預期輸出：orbstack

# 確認 K8s nodes 正常
kubectl get nodes
# 預期：一個 Node，STATUS Ready

# 確認靶機 image 已在本地（compose build 建出來的）
docker images loadtest-app
# 預期輸出包含一行：loadtest-app   stage2   ...
```

**若上面沒有任何輸出**（image 還沒 build 過），先執行這步再繼續：

```bash
docker compose build app
```

> OrbStack 教學點：OrbStack 的 K8s 與 Docker daemon 共用同一個 containerd image store。
> compose build 出來的 image 直接就在 K8s 可存取的地方，不需要推 registry。
> 這就是為什麼 app.yaml 裡用 `imagePullPolicy: Never`。

---

## 二、部署順序（apply 有先後依賴）

```bash
# 1. 建立 namespace（其他所有資源都在這個 namespace 裡）
kubectl apply -f k8s/namespace.yaml

# 2. 部署 DB（ConfigMap + Secret + Deployment + Service 都在同一個 db.yaml）
kubectl apply -f k8s/db.yaml

# 3. 部署靶機（ConfigMap + Deployment + Service 都在同一個 app.yaml）
kubectl apply -f k8s/app.yaml
```

或一次 apply 整個目錄（K8s 會自己處理順序，但 namespace 要先存在）：

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
```

---

## 三、驗證：確認所有東西都起來了

### 3-1. 看 Pod 狀態

```bash
kubectl get pods -n loadtest -w
# -w (watch)：即時更新，看 Pod 從 Pending → Init → Running → Ready
```

預期輸出（約 30~60 秒後）：

```
NAME                   READY   STATUS    RESTARTS   AGE
app-xxxxxxxxx-xxxxx    1/1     Running   0          60s
db-xxxxxxxxxx-xxxxx    1/1     Running   0          90s
```

如果 Pod 卡住，看原因：

```bash
kubectl describe pod -n loadtest -l app=db   # 看 DB Pod 的事件
kubectl describe pod -n loadtest -l app=app  # 看 App Pod 的事件
kubectl logs -n loadtest -l app=db           # 看 DB 的 stdout log
kubectl logs -n loadtest -l app=app          # 看 App 的 stdout log
```

### 3-2. 看 Service 和 EXTERNAL-IP

```bash
kubectl get svc -n loadtest
```

預期輸出：

```
NAME   TYPE           CLUSTER-IP      EXTERNAL-IP     PORT(S)          AGE
app    LoadBalancer   10.96.xxx.xxx   <EXTERNAL-IP>   8000:3xxxx/TCP   60s
db     ClusterIP      10.96.xxx.xxx   <none>          5432/TCP         90s
```

DB Service 是 ClusterIP（叢集內用，沒有 EXTERNAL-IP，正確）。
App Service 是 LoadBalancer（OrbStack 會分配 EXTERNAL-IP）。

### 3-3. 打 /healthz 確認靶機活著

```bash
# 取得 EXTERNAL-IP（OrbStack LoadBalancer）
APP_IP=$(kubectl get svc app -n loadtest -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "靶機 IP: $APP_IP"

curl http://$APP_IP:8000/healthz
# 預期：{"status":"ok"}

curl http://$APP_IP:8000/readyz
# 預期：{"status":"ready"}

curl http://$APP_IP:8000/docs
# 或在瀏覽器打開 http://<EXTERNAL-IP>:8000/docs 看 Swagger UI
```

> 如果 OrbStack 還沒分配 EXTERNAL-IP（Pending 狀態），改用 port-forward：
> ```bash
> kubectl port-forward -n loadtest svc/app 8000:8000
> # 然後 curl http://localhost:8000/healthz
> ```

---

## 四、用 host 上的 Locust 打 K8s 靶機

Locust 在 host 上跑（不進 K8s），直接打 LoadBalancer 的 EXTERNAL-IP：

```bash
# 取得靶機 IP（只需要執行一次）
APP_IP=$(kubectl get svc app -n loadtest -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# 啟動 Locust Web UI，指向 K8s 靶機（host 上用 uv run，repo 慣例）
uv run locust -f locustfiles/demo1_basics.py --host http://$APP_IP:8000 --class-picker

# 或 headless 一次跑（對齊 compose 的 headless 指令格式）
uv run locust -f locustfiles/demo4_sync_vs_async_db.py \
  --host http://$APP_IP:8000 \
  --headless -u 50 -r 10 -t 60s
```

換 demo 腳本：直接換 `-f` 的參數即可，不需要重新部署靶機。

---

## 五、監控 K8s Pod 資源用量（對照 docker stats）

```bash
# 即時 CPU / Memory 用量（對應 compose 模式的 docker stats）
kubectl top pod -n loadtest

# 持續觀察（-w 不支援 top，用 watch 指令替代）
watch kubectl top pod -n loadtest
```

看 Deployment 的滾動更新狀態：

```bash
kubectl rollout status deployment/app -n loadtest
```

---

## 六、實驗旋鈕：改 DB_POOL_SIZE（demo5 式實驗）

K8s 模式的旋鈕操作方式：

```bash
# 把 pool 從 5 調到 100（不需要重 build image）
kubectl patch configmap app-config -n loadtest \
  --patch '{"data":{"DB_POOL_SIZE":"100"}}'

# 讓 app Deployment 滾動重啟，讓新的 env 值生效
kubectl rollout restart deployment/app -n loadtest

# 等新 Pod 就緒
kubectl rollout status deployment/app -n loadtest

# 確認新 pool 大小已生效（看 Pod 環境變數）
kubectl exec -n loadtest deploy/app -- env | grep DB_POOL_SIZE
```

> ⚠️ 兩個真實踩過的坑：
> 1. **patch 會被 apply 蓋掉**：`kubectl patch` 是 imperative 的暫時操作，
>    下次 `kubectl apply -f k8s/app.yaml` 會把 ConfigMap 蓋回宣告的 "5"。
>    實驗完想保留設定，就改 app.yaml 裡的值再 apply（declarative 才是真相）。
> 2. **pool=100 時一個 Pod 就吃滿 PG 連線預算**（sync + async 兩個 engine 各開
>    pool=100，見根目錄 README「兩個 SQLAlchemy Engine」章節；100×2 = 200 = max_connections）。
>    app Deployment 因此用 `Recreate` 策略 —— RollingUpdate 新舊並存需要雙倍連線，
>    新 Pod 會撞 `FATAL: sorry, too many clients already` 然後 rollout 死鎖
>    （完整教學註解見 app.yaml 的 strategy 段落）。
> 3. **改 ConfigMap 不會自動生效**：`configMapKeyRef` 的 env 只在容器啟動時讀一次。
>    apply 改了 ConfigMap 但 Deployment 模板沒變 → 不觸發 rollout → 跑著的 Pod
>    還拿著舊值。必須 `kubectl rollout restart` 才收斂 —— 驗證方式就是上面的
>    `kubectl exec ... env | grep DB_POOL_SIZE`。

改回來：

```bash
kubectl patch configmap app-config -n loadtest \
  --patch '{"data":{"DB_POOL_SIZE":"5"}}'
kubectl rollout restart deployment/app -n loadtest
```

---

## 七、單 Pod K8s Baseline vs Compose Baseline 對比實驗

> 壓注：K8s 的靶機（單 Pod）vs compose 的靶機，相同 demo4 腳本（100 users, delay_ms=100, pool=100），
> RPS 和 p95 應該接近，差異主要來自 CPU 調度機制不同（cpuset vs CFS quota）。

### 押注 → 跑 → 對答案的節奏

| 步驟 | Compose 模式 | K8s 模式 |
|------|-------------|---------|
| 靶機限制 | cpuset "2,3"（鎖死核心 2、3） | cpu limit "2"（CFS quota，可跨核） |
| 攻擊機 | compose 內的 locust container，cpuset "4-7" | host 上的 locust，沒有 cpuset |
| 打法 | `docker compose run --rm locust -f /mnt/locust/demo4...` | `uv run locust -f locustfiles/demo4... --host http://$APP_IP:8000` |
| 監控 | `docker stats` | `kubectl top pod -n loadtest` |

**在跑之前，先押注：**
1. K8s 模式的 async RPS 會比 compose 模式高還是低？為什麼？
2. p95 latency 會比 compose 模式高還是低？
3. DB 的 CPU 用量會佔多少？（K8s 下 DB 和 App 可能搶同一顆核心）

**跑完記錄，對答案：**
- 如果 K8s RPS 明顯低於 compose：很可能是 CPU scheduling 差異（沒有 cpuset 隔離）
- 如果 RPS 接近：說明 CFS quota 在這個壓力下跟 cpuset 行為差不多

> ✅ 已驗證數據（2026-06-05，AsyncPostsUser 100 users / delay_ms=100 / pool=100 / 60s）
>
> | 模式 | RPS | p50 | p95 | 靶機 CPU |
> | --- | --- | --- | --- | --- |
> | compose（cpuset 隔離，容器內攻擊） | 512 | 200ms | N/A | N/A |
> | K8s 單 Pod（CFS quota，host 攻擊） | 440 | 180ms | 450ms | 648m |
>
> 對答案：RPS 低 ~14%、p50 反而略好 —— 差異來自「攻擊機在 host 上與 VM 共擠」
> + kube-proxy/LoadBalancer 多一跳 + CFS quota 無核心隔離。
> 量級一致 → 單 Pod K8s baseline 成立，階段三從這裡起跳。
>
> 註：compose 的 p95/CPU 當初未記錄（N/A），「p95 押注」留待補測對答案；
> 648m = 0.648 vCPU（K8s 的 millicpu 單位）—— 已超過 requests 500m、離 limit 2000m 還遠。

這個對比是階段三（多 Pod + HPA）的起點：知道單 Pod K8s 的 baseline，
才能評估加 replicas 後 scale-out 的效益。

---

## 八、清理

```bash
# 刪掉所有資源（namespace 下的全部 K8s 物件）
kubectl delete namespace loadtest

# 或只刪 app / db，保留 namespace（下次 apply 更快）
kubectl delete -f k8s/app.yaml
kubectl delete -f k8s/db.yaml
```

> 注意：DB 用 emptyDir（沒有 PVC），Pod 刪掉資料就沒了，
> 下次 `kubectl apply -f k8s/db.yaml` 重新部署時 init.sql 會重新執行，
> 資料回到 50 users / 200 posts 的 seed 狀態——和 compose 的行為一致。

---

## 附錄：K8s 檔案結構說明

```
k8s/
├── namespace.yaml   # loadtest namespace（先 apply）
├── db.yaml          # ConfigMap（init.sql）+ Secret（帳密）
│                    # + Deployment（postgres）+ Service（ClusterIP）
├── app.yaml         # ConfigMap（DB_POOL_SIZE）
│                    # + Deployment（靶機）+ Service（LoadBalancer）
└── README.md        # 本文件
```

各資源的依賴關係：

```
namespace.yaml
    └── db.yaml（ConfigMap → Secret → Deployment → Service）
            └── app.yaml（ConfigMap → Deployment（refs db Service DNS）→ Service）
```

---

## 下一步（階段三）

- [ ] 加 `replicas: 3`，觀察 pool starvation 如何隨 Pod 數變化
- [ ] 加 HPA（基於 CPU 使用率自動擴縮）
- [ ] 把 Locust 也上 K8s（Master-Worker 分散式壓測）
- [ ] 加 Prometheus + Grafana 觀測（`kubectl top` 只是起點）
