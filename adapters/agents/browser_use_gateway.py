"""BrowserUseGateway：以 browser-use 實作 BrowserAgentPort。

本類別是純映射器（adapters 層）：不認得 infrastructure，也不自己建 LLM。
建立 browser-use Agent 的工廠由外部（infrastructure 組裝根）注入，
這樣依賴方向維持由外指向內。單元測試注入 fake agent factory 驗證映射。
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from domain.ports import StepCallback
from domain.steering import SteeringControl
from domain.value_objects import AgentRunResult, AgentStep

logger = logging.getLogger(__name__)
_PAUSE_POLL_SECONDS = 0.05

# 工廠：依 task 與（async）step callback 產生一個有 async run(max_steps) 的 agent。
AgentFactory = Callable[..., Any]
BUStepCallback = Callable[..., Awaitable[None]]

# C2: 登入頁 URL 與 title 偵測規則（infrastructure 關注點，不進 domain）。
_LOGIN_URL_PATTERNS = (
    "accounts.google.com",
    "login.microsoftonline.com",
    "login.live.com",
    "/login",
    "/signin",
    "/sign-in",
    "/auth/login",
)
_LOGIN_TITLE_KEYWORDS = ("sign in", "log in", "login", "登入")

# session-persist: 跨任務登入持久化（每網域一個 JSON 檔）
_SESSION_DIR = Path("workspace/sessions/cookies")


def _detect_login_page(url: str, title: str) -> bool:
    """判斷當前頁面是否為登入頁（URL 或 title 含登入關鍵字）。"""
    u = url.lower()
    t = title.lower()
    return any(p in u for p in _LOGIN_URL_PATTERNS) or any(
        k in t for k in _LOGIN_TITLE_KEYWORDS
    )


def _session_path(url: str) -> Path | None:
    try:
        host = urlparse(url).hostname or ""
        if not host:
            return None
        domain = host.removeprefix("www.")
        return _SESSION_DIR / f"{domain}.json"
    except Exception:  # noqa: BLE001
        return None


def _load_session(url: str) -> dict | None:
    path = _session_path(url)
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _save_session(url: str, state: dict) -> None:
    path = _session_path(url)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        logger.info("C2: session saved to %s", path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("C2: session save failed: %s", exc)


class BrowserUseGateway:
    def __init__(self, *, agent_factory: AgentFactory) -> None:
        self._agent_factory = agent_factory

    async def run(
        self,
        instruction: str,
        *,
        start_url: str | None = None,
        max_steps: int = 40,
        on_step: StepCallback | None = None,
        control: SteeringControl | None = None,
        sensitive_data: dict | None = None,
        allowed_domains: list[str] | None = None,
        download_dir: Path | None = None,
        user_data_dir: Path | None = None,
    ) -> AgentRunResult:
        task_text = instruction
        if start_url and start_url not in instruction:
            task_text = f"{instruction}\nStart at: {start_url}"

        steps: list[AgentStep] = []
        # C3: 用 closure set 在每個 step 累積下載檔案。
        # 利用「bu_step_cb 在 done action 執行前觸發」的時間窗口，
        # 確保 _downloaded_files 被 reset() 清空前已被記錄。
        _seen_artifacts: set[str] = set()
        # B8: token 用量統計（跨所有 attempt 累積）
        token_stats: dict = {"input": 0, "output": 0, "calls": 0}
        login_emitted: list[bool] = [False]
        # session-persist: 優先從磁碟載入已持久化的登入狀態
        initial_storage = _load_session(start_url) if start_url else None
        if initial_storage:
            logger.info("C2: loaded persisted session for %s", start_url)
        saved_storage_state: list[dict | None] = [initial_storage]
        agent: Any = None  # 由 closure 引用，每個 attempt 重新賦值

        # C2-Redesign: 讓自訂 Action（request_human_action）得以發事件 + 儲存 session
        def _login_step_emitter(message: str, url: str | None) -> None:
            """自訂 Action 呼叫：透過標準 on_step 管道發 clarification 步驟事件。"""
            if not login_emitted[0]:
                login_emitted[0] = True
            step = AgentStep(
                description=f"等待使用者：{message}",
                login_detected=True,
                login_url=url,
            )
            if on_step is not None:
                on_step(step)

        def _session_saver(state: dict) -> None:
            """自訂 Action 呼叫：儲存匯出的 cookies 供 retry fallback 及跨任務持久化。"""
            saved_storage_state[0] = state
            n = len(state.get("cookies", []))
            logger.info("C2: request_human_action saved storage_state, cookies=%d", n)
            if start_url:
                _save_session(start_url, state)

        async def bu_step_cb(browser_state: Any, agent_output: Any, n_steps: int) -> None:
            # C1: 取 LLM 推理摘要（用 getattr 容忍版本差異及 None）
            thought = getattr(agent_output, "thinking", None) if agent_output else None
            next_goal = getattr(agent_output, "next_goal", None) if agent_output else None
            evaluation = (
                getattr(agent_output, "evaluation_previous_goal", None)
                if agent_output
                else None
            )

            url = getattr(browser_state, "url", "") or ""
            title = getattr(browser_state, "title", "") or ""

            # C2-Redesign: 檢查 LLM 是否已選擇 request_human_action（Primary 路徑）
            # 若是，自訂 Action 本身負責 pause + export + save，此處不再重複
            action_list = getattr(agent_output, "action", None) or []
            llm_used_human_action = any(
                getattr(a, "request_human_action", None) is not None
                for a in action_list
            )

            if llm_used_human_action:
                # Primary 路徑：login_emitted 已由 _login_step_emitter 設定
                # 仍建立 login_detected 步驟，讓狀態機正確推進
                is_login = True
            else:
                # Fallback 路徑：LLM 未呼叫自訂 action，URL 偵測補位
                is_login = _detect_login_page(url, title) and not login_emitted[0]

            step = AgentStep(
                description=f"step {n_steps}",
                thought=thought,
                next_goal=next_goal,
                evaluation=evaluation,
                login_detected=is_login,
                login_url=url if is_login else None,
            )
            steps.append(step)

            # 即時轉向：先 drain 並處理 stop
            if control is not None:
                for msg in control.drain():
                    agent.add_new_task(msg)
                if control.stopped:
                    agent.stop()
                    return

            # Fallback 路徑：URL 偵測觸發時才標記 login_emitted
            if is_login and not llm_used_human_action:
                login_emitted[0] = True

            # C3: 在每步抓取已下載檔案（done action 尚未執行，list 尚未被 reset() 清空）
            try:
                bs = getattr(agent, "browser_session", None)
                for fpath in getattr(bs, "downloaded_files", None) or []:
                    fname = Path(fpath).name
                    if fname:
                        _seen_artifacts.add(fname)
            except Exception:  # noqa: BLE001
                pass

            # 發步驟事件（RunBrowserJob on_step 負責發 think + step + clarification）
            if on_step is not None:
                on_step(step)

            # C2 Fallback pause（僅在 LLM 未用 request_human_action 時才介入）
            # Primary 路徑由 request_human_action action 本身處理 pause
            if control is not None and not llm_used_human_action:
                if is_login:
                    control.pause()
                while control.paused and not control.stopped:
                    await asyncio.sleep(_PAUSE_POLL_SECONDS)

                # Fallback storage_state 匯出（LLM 選 done 時的最後防線）
                if is_login and not control.paused and not control.stopped:
                    bs = getattr(agent, "browser_session", None)
                    if bs is not None and hasattr(bs, "export_storage_state"):
                        try:
                            saved_storage_state[0] = await bs.export_storage_state()
                            n_cookies = len(
                                (saved_storage_state[0] or {}).get("cookies", [])
                            )
                            logger.info(
                                "C2 fallback: storage_state captured, cookies=%d",
                                n_cookies,
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "C2 fallback: export_storage_state failed: %s", exc
                            )
                        else:
                            if start_url and saved_storage_state[0]:
                                _save_session(start_url, saved_storage_state[0])

        current_task = task_text

        for _attempt in range(3):  # 初始 + 最多 2 次登入 fallback 重啟
            logger.info(
                "C2: attempt=%d, storage_state=%s",
                _attempt,
                "yes" if saved_storage_state[0] else "no",
            )
            agent = self._agent_factory(
                task=current_task,
                on_step=bu_step_cb,
                sensitive_data=sensitive_data,
                allowed_domains=allowed_domains,
                download_dir=download_dir,
                user_data_dir=user_data_dir,
                storage_state=saved_storage_state[0],
                # C2-Redesign: 注入自訂 Action 所需的回調
                control=control,
                login_step_emitter=_login_step_emitter,
                session_saver=_session_saver,
                # B8: 對話日誌
                save_log_path=(
                    user_data_dir / f"conversation_{_attempt}.json"
                    if user_data_dir
                    else None
                ),
            )
            history = await agent.run(max_steps=max_steps)

            # B8: 從 history.usage（browser-use 內建 UsageSummary）累積 token 用量
            try:
                u = getattr(history, "usage", None)
                if u is not None:
                    token_stats["input"]  += getattr(u, "total_prompt_tokens",     0)
                    token_stats["output"] += getattr(u, "total_completion_tokens", 0)
                    token_stats["calls"]  += getattr(u, "entry_count",             0)
                    cost = getattr(u, "total_cost", None)
                    if cost:
                        token_stats["cost"] = token_stats.get("cost", 0.0) + cost
            except Exception:  # noqa: BLE001
                pass

            logger.info(
                "C2: history success=%s, login_emitted=%s",
                history.is_successful(),
                login_emitted[0],
            )

            # 若本輪偵測到登入且 agent 失敗 → storage_state 已在 bu_step_cb 內匯出，
            # 重置 flag，下一輪用已登入的 cookies 重新啟動。
            if not history.is_successful() and login_emitted[0]:
                user_stopped = control is not None and control.stopped
                if not user_stopped:
                    login_emitted[0] = False  # 重置，讓新 run 可再偵測
                    current_task = (
                        task_text + "\n\n[使用者已完成登入。請從頭繼續執行原始任務。]"
                    )
                    continue

            break  # 成功、或非登入失敗、或使用者停止

        # B8: 記錄 token 用量（來自 history.usage，含 browser-use 按模型定價計算的成本）
        if token_stats["calls"] > 0:
            logger.info(
                "B8 token usage: input=%d output=%d calls=%d cost=$%.4f",
                token_stats["input"],
                token_stats["output"],
                token_stats["calls"],
                token_stats.get("cost", 0.0),
            )

        # C3: 三重保障取得已下載檔案
        # 1. step callback 累積（_seen_artifacts，CDP 非同步時序不保證完整）
        # 2. history 的 done action attachments（終端機 log 中的 files_to_display，最直接）
        # 3. 目錄掃描（磁碟上的實體檔案，不受 reset() 影響，最終補底）

        history_artifacts: set[str] = set()
        try:
            if history.history:
                for result in history.history[-1].result or []:
                    for fpath in result.attachments or []:
                        fname = Path(fpath).name
                        if fname:
                            history_artifacts.add(fname)
        except Exception:  # noqa: BLE001
            pass

        dir_artifacts: set[str] = set()
        if download_dir is not None and download_dir.is_dir():
            try:
                dir_artifacts = {f.name for f in download_dir.iterdir() if f.is_file()}
            except Exception:  # noqa: BLE001
                pass

        all_artifacts = tuple(sorted(_seen_artifacts | history_artifacts | dir_artifacts))

        success = bool(history.is_successful())
        final = history.final_result()
        if success:
            return AgentRunResult(
                success=True,
                output=final,
                steps=tuple(steps),
                error=None,
                artifacts=all_artifacts,
                token_stats=dict(token_stats),
            )
        return AgentRunResult(
            success=False,
            output=None,
            steps=tuple(steps),
            error=final or "agent 未完成任務",
            artifacts=all_artifacts,
            token_stats=dict(token_stats),
        )
