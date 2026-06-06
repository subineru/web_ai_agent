"""務實版 RLHF 的「下次更好」核心（純邏輯）。

不微調權重，而是把成功經驗與使用者回饋沉澱成 LearnedTool，
下次同網域任務時，把它們當 few-shot 附加到指示中，提升成功率。
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

SUCCESS = "success"
FEEDBACK = "feedback"


@dataclass(frozen=True)
class LearnedTool:
    site_domain: str
    instruction: str
    guidance: str
    kind: str  # "success" | "feedback"

    def __post_init__(self) -> None:
        if not self.guidance.strip():
            raise ValueError("LearnedTool.guidance 不可為空白")


def augment_instruction(instruction: str, tools: Sequence[LearnedTool]) -> str:
    """把先前經驗附加到指示後面，作為 few-shot 提示。無經驗則原樣回傳。"""
    if not tools:
        return instruction
    lines = ["", "先前在此網站的相關經驗（請參考以提升成功率）："]
    for t in tools:
        tag = "✅ 成功經驗" if t.kind == SUCCESS else "✏️ 使用者修正"
        lines.append(f"- [{tag}] {t.guidance}")
    return instruction + "\n" + "\n".join(lines)
