"""依實際程式碼結構，重寫 README.md 中的 Mermaid 架構圖。

只替換 `<!-- ARCH:START -->` 與 `<!-- ARCH:END -->` 之間的內容，其餘不動。
輸出確定性（排序固定），CI 可用 --check 做 diff 檢查。

用法：
    uv run python scripts/gen_readme_diagram.py
    uv run python scripts/gen_readme_diagram.py --check
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 重用 repo map 的掃描器
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_repo_map import ROOT, scan_project  # noqa: E402

README = ROOT / "README.md"
START = "<!-- ARCH:START -->"
END = "<!-- ARCH:END -->"

# Clean Architecture 由外到內的層級顯示順序與標題
LAYER_TITLES = {
    "domain": "Domain（最內・純邏輯）",
    "application": "Application（Use Cases）",
    "adapters": "Adapter / Interface",
    "infrastructure": "Infrastructure（最外）",
}


def _node_id(path: str) -> str:
    return path.replace("/", "_").replace(".py", "").replace("-", "_")


def build_mermaid() -> str:
    modules = scan_project()
    by_layer: dict[str, list[str]] = {}
    for m in modules:
        layer = m.path.split("/")[0]
        if layer in LAYER_TITLES:
            by_layer.setdefault(layer, []).append(m.path)

    lines = ["```mermaid", "flowchart TB"]
    for layer in LAYER_TITLES:  # 固定順序：外 → 內
        paths = sorted(by_layer.get(layer, []))
        lines.append(f'    subgraph {layer}["{LAYER_TITLES[layer]}"]')
        if paths:
            for p in paths:
                label = p.split("/", 1)[1] if "/" in p else p
                lines.append(f'        {_node_id(p)}["{label}"]')
        else:
            lines.append(f'        {layer}_empty["（待實作）"]')
        lines.append("    end")
    # 依賴方向：外層指向內層（Clean Architecture）
    lines.append("    infrastructure --> adapters --> application --> domain")
    lines.append("```")
    return "\n".join(lines)


def render_block() -> str:
    return f"{START}\n{build_mermaid()}\n{END}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not README.exists():
        print("README.md 不存在，請先建立並加入 ARCH 標記區段", file=sys.stderr)
        return 1

    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print(f"README.md 缺少 {START} / {END} 標記", file=sys.stderr)
        return 1

    pre = text.split(START)[0]
    post = text.split(END, 1)[1]
    new_text = pre + render_block() + post

    if args.check:
        if new_text != text:
            print("README 架構圖過期，請執行：uv run python scripts/gen_readme_diagram.py", file=sys.stderr)
            return 1
        print("README 架構圖是最新的")
        return 0

    if new_text != text:
        README.write_text(new_text, encoding="utf-8")
        print("已更新 README.md 架構圖")
    else:
        print("README 架構圖無變動")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
