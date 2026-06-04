"""開發用入口：`uv run main.py` 直接起服務（含 hot-reload）。

壓測時不要用 reload 模式，改跑：
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

固定 1 個 worker 是刻意的 —— 先看清楚「單一 event loop」的行為，
再談 multi-worker / 水平擴展。
"""

import uvicorn


def main() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
