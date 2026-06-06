"""產生 repo map：掃描專案 Python 套件，輸出 docs/repo-map/REPO_MAP.md。

輸出必須是「確定性」的（排序固定），CI 才能用 diff 檢查是否與程式碼一致。

用法：
    uv run python scripts/gen_repo_map.py          # 重寫 docs/repo-map/REPO_MAP.md
    uv run python scripts/gen_repo_map.py --check   # 不寫檔，若會變動則 exit 1（CI 用）
"""
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 掃描這些分層套件（Clean Architecture）
LAYERS = ["domain", "application", "adapters", "infrastructure", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".venv", "node_modules", "outputs", "state"}
OUT_FILE = ROOT / "docs" / "repo-map" / "REPO_MAP.md"


@dataclass
class FuncInfo:
    name: str
    args: list[str]
    is_async: bool


@dataclass
class ClassInfo:
    name: str
    bases: list[str]
    methods: list[FuncInfo] = field(default_factory=list)


@dataclass
class ModuleInfo:
    path: str  # 相對 ROOT 的 posix 路徑
    doc: str
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FuncInfo] = field(default_factory=list)


def _sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FuncInfo:
    args = [a.arg for a in node.args.args if a.arg != "self"]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    return FuncInfo(name=node.name, args=args, is_async=isinstance(node, ast.AsyncFunctionDef))


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ast.unparse(node)


def parse_module(py: Path) -> ModuleInfo:
    tree = ast.parse(py.read_text(encoding="utf-8"))
    mod = ModuleInfo(path=py.relative_to(ROOT).as_posix(), doc=(ast.get_docstring(tree) or "").split("\n")[0])
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            ci = ClassInfo(name=node.name, bases=[_base_name(b) for b in node.bases])
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not sub.name.startswith("_"):
                    ci.methods.append(_sig(sub))
            mod.classes.append(ci)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            mod.functions.append(_sig(node))
    return mod


def scan_project() -> list[ModuleInfo]:
    modules: list[ModuleInfo] = []
    for layer in LAYERS:
        base = ROOT / layer
        if not base.exists():
            continue
        for py in sorted(base.rglob("*.py")):
            if any(part in EXCLUDE_DIRS for part in py.parts):
                continue
            if py.name == "__init__.py" and py.stat().st_size == 0:
                continue
            modules.append(parse_module(py))
    return modules


def _fmt_func(f: FuncInfo) -> str:
    prefix = "async " if f.is_async else ""
    return f"{prefix}{f.name}({', '.join(f.args)})"


def render(modules: list[ModuleInfo]) -> str:
    lines = [
        "# Repo Map",
        "",
        "> 自動產生，請勿手改。由 `scripts/gen_repo_map.py` 維護，PostToolUse hook 在每次改 .py 後重生。",
        "",
        f"模組總數：{len(modules)}",
        "",
    ]
    current_layer = None
    for m in modules:
        layer = m.path.split("/")[0]
        if layer != current_layer:
            current_layer = layer
            lines.append(f"## {layer}/")
            lines.append("")
        lines.append(f"### `{m.path}`")
        if m.doc:
            lines.append(f"_{m.doc}_")
        for c in m.classes:
            bases = f"({', '.join(c.bases)})" if c.bases else ""
            lines.append(f"- **class {c.name}{bases}**")
            for meth in c.methods:
                lines.append(f"  - `{_fmt_func(meth)}`")
        for fn in m.functions:
            lines.append(f"- `{_fmt_func(fn)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只檢查是否最新，不寫檔（CI 用）")
    args = ap.parse_args()

    content = render(scan_project())
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = OUT_FILE.read_text(encoding="utf-8") if OUT_FILE.exists() else ""

    if args.check:
        if existing != content:
            print("repo map 過期，請執行：uv run python scripts/gen_repo_map.py", file=sys.stderr)
            return 1
        print("repo map 是最新的")
        return 0

    if existing != content:
        OUT_FILE.write_text(content, encoding="utf-8")
        print(f"已更新 {OUT_FILE.relative_to(ROOT)}")
    else:
        print("repo map 無變動")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
