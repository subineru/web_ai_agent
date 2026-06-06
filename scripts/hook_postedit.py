"""PostToolUse hook：當有 .py 檔被編輯時，自動重生 repo map 與 README 架構圖。

由 .claude/settings.json 的 PostToolUse hook 呼叫。讀 stdin 的 JSON
（Claude Code 提供 tool 輸入），只在編輯到 .py 時才重生，避免無謂開銷。
寫出的是 .md 檔，不會再觸發本 hook（matcher 僅針對 .py 編輯），無遞迴風險。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _edited_paths(payload: dict) -> list[str]:
    ti = payload.get("tool_input", {}) or {}
    paths: list[str] = []
    for key in ("file_path", "path"):
        if ti.get(key):
            paths.append(str(ti[key]))
    # MultiEdit 等可能帶 edits 陣列
    for edit in ti.get("edits", []) or []:
        if isinstance(edit, dict) and edit.get("file_path"):
            paths.append(str(edit["file_path"]))
    return paths


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # 沒有有效輸入就安靜結束，不阻擋

    if not any(p.endswith(".py") for p in _edited_paths(payload)):
        return 0

    for script in ("gen_repo_map.py", "gen_readme_diagram.py"):
        subprocess.run(
            ["uv", "run", "python", str(ROOT / "scripts" / script)],
            cwd=ROOT,
            capture_output=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
