# 靶機（FastAPI）的 multi-stage build。
#
# Stage 1（builder）：用 uv 官方 image 裝依賴 —— uv.lock 鎖定版本，
#   只 bind-mount lock 檔不 COPY 程式碼，改 app/ 不會打掉依賴層的 cache。
# Stage 2（runtime）：乾淨的 python slim，只帶 .venv + 程式碼，
#   不含 uv、不含 dev 依賴（locust 屬於攻擊機，不該出現在靶機 image 裡）。
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# 只裝依賴（--no-install-project）：本專案沒有 build-system，本來就只是依賴的載體
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project


FROM python:3.13-slim-bookworm

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app/ app/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# 與壓測 runbook 一致：關 access log、固定 1 worker（先看清單一 event loop）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
