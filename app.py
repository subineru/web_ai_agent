"""wagent 統一入口：一行同時跑真實後端 + 前端。

    uv run python app.py

會自動：偵測前端是否已 build；若未 build 則 npm install + npm run build，
然後用 FastAPI 單一程序同時服務 React 前端與 API（單一 port），最後啟動伺服器。
開 http://localhost:8000 即完整系統（真實 browser-use + .env 金鑰 + sqlite）。

參數：
    --host 127.0.0.1   綁定位址
    --port 8000        埠號
    --skip-build       略過自動 build（直接用現有 frontend/dist）
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"

# Windows 主控台預設 cp950 會無法輸出 emoji/中文，統一改 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def _npm() -> str:
    npm = shutil.which("npm")
    if npm is None:
        sys.exit(
            "找不到 npm。請先安裝 Node.js（https://nodejs.org），或先在別處 build 前端後用 --skip-build。"
        )
    return npm


def ensure_frontend_built(skip_build: bool) -> bool:
    """確保 frontend/dist 存在。回傳是否有可服務的前端。"""
    if (DIST / "index.html").exists():
        return True
    if skip_build:
        print("⚠️  frontend/dist 不存在且指定了 --skip-build，將只提供 API（無前端頁面）。")
        return False

    npm = _npm()
    if not (FRONTEND / "node_modules").exists():
        print("📦 安裝前端相依套件（npm install）…")
        subprocess.run([npm, "install"], cwd=FRONTEND, check=True)
    print("🏗️  建置前端（npm run build）…")
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)
    return (DIST / "index.html").exists()


def main() -> None:
    parser = argparse.ArgumentParser(description="wagent 統一啟動器")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    has_frontend = ensure_frontend_built(args.skip_build)

    # 延遲 import，確保 build 訊息先出現、也讓 --help 不需載入重相依
    import uvicorn

    from infrastructure.container import Container
    from infrastructure.web import create_app

    app = create_app(Container.create(), static_dir=DIST if has_frontend else None)

    url = f"http://{args.host}:{args.port}"
    print(f"\n🚀 wagent 已啟動：{url}")
    if has_frontend:
        print(f"   開啟瀏覽器 → {url}")
    print(f"   API 文件 → {url}/docs\n")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
