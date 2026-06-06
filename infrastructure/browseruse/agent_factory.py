"""真實 browser-use Agent 工廠（Infrastructure 組裝根）。

這裡才 import browser-use 與 infrastructure.llm（合法：infrastructure 在最外層）。
產出的工廠注入給 adapters 的 BrowserUseGateway，讓 gateway 不需依賴 infrastructure。
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from infrastructure.config import Settings, get_settings
from infrastructure.llm.factory import build_fallback_llm, build_llm

BUStepCallback = Callable[..., Awaitable[None]]

# C2-Redesign: 通知前端的回調型別（message, current_url|None）
LoginStepEmitter = Callable[[str, "str | None"], None]
SessionSaver = Callable[[dict], None]

_HUMAN_ACTION_SYSTEM_HINT = (
    "當你遇到登入頁面、CAPTCHA 或其他需要人工操作的情況時，"
    "請優先使用 request_human_action 工具，說明需要人工完成的操作。"
    "等待人工操作完成後，你可以從當前頁面繼續執行任務，不需要重頭開始。"
    "只有在任務本身已完成或完全無法繼續時才使用 done。"
)


def make_browser_use_agent_factory(settings: Settings | None = None) -> Callable[..., Any]:
    s = settings or get_settings()

    def factory(
        *,
        task: str,
        on_step: BUStepCallback,
        sensitive_data: dict | None = None,
        allowed_domains: list[str] | None = None,
        download_dir: Path | None = None,
        user_data_dir: Path | None = None,
        storage_state: dict | None = None,
        # C2-Redesign: 自訂 Action 的注入點（皆可 None，向後相容）
        control: Any = None,
        login_step_emitter: LoginStepEmitter | None = None,
        session_saver: SessionSaver | None = None,
    ) -> Any:
        from browser_use import Agent, BrowserProfile, Controller
        from browser_use.agent.views import ActionResult
        from pydantic import BaseModel

        class _RequestHumanActionParams(BaseModel):
            message: str  # LLM 說明需要人工完成的操作

        controller = Controller()

        @controller.action(
            "向使用者請求手動操作（例如登入帳號、解 CAPTCHA、授權確認）。"
            "當頁面需要人工介入且你無法自動完成時使用；"
            "使用者完成操作後，你可以從當前頁面繼續任務，無需重新開始。",
            param_model=_RequestHumanActionParams,
        )
        async def request_human_action(
            params: _RequestHumanActionParams,
            browser_session,  # 無型別註解：避免 PEP 563 字串化導致 registry 特殊參數驗證失敗
        ) -> ActionResult:
            # 1. 讀取當前真實 URL（browser-use 可能還在登入頁，讓 emitter 知道）
            current_url: str | None = None
            try:
                focus_id = getattr(browser_session, "agent_focus_target_id", None)
                sm = getattr(browser_session, "session_manager", None)
                if focus_id and sm and hasattr(sm, "get_target"):
                    t = sm.get_target(focus_id)
                    current_url = getattr(t, "url", None) or None
            except Exception:  # noqa: BLE001
                pass

            # 2. 通知前端（發 step 事件，含 login_detected=True，觸發 clarification UI）
            if login_step_emitter is not None:
                login_step_emitter(params.message, current_url)

            # 3. 暫停等待使用者完成操作
            if control is not None:
                control.pause()
                while control.paused and not control.stopped:
                    await asyncio.sleep(0.05)

            # 4. 使用者操作完成後，匯出 cookies 並持久化
            if hasattr(browser_session, "export_storage_state"):
                try:
                    state = await browser_session.export_storage_state()
                    if state and session_saver is not None:
                        session_saver(state)
                except Exception:  # noqa: BLE001
                    pass

            return ActionResult(
                extracted_content=(
                    "使用者已完成所請求的操作，請確認瀏覽器當前頁面並繼續任務。"
                ),
                long_term_memory=(
                    "人工操作已完成，瀏覽器狀態已更新，可從當前頁面繼續執行。"
                ),
            )

        kwargs: dict[str, Any] = dict(
            task=task,
            llm=build_llm(s),
            fallback_llm=build_fallback_llm(s),
            max_failures=s.max_failures,
            register_new_step_callback=on_step,
            controller=controller,
            extend_system_message=_HUMAN_ACTION_SYSTEM_HINT,
        )

        # BrowserProfile: keep_alive=True + 可選 storage_state（已登入 cookies）
        profile_kwargs: dict[str, Any] = {"headless": s.headless, "keep_alive": True}
        if download_dir is not None:
            download_dir.mkdir(parents=True, exist_ok=True)
            profile_kwargs["downloads_path"] = download_dir
        if user_data_dir is not None:
            user_data_dir.mkdir(parents=True, exist_ok=True)
            profile_kwargs["user_data_dir"] = user_data_dir
        if storage_state is not None:
            profile_kwargs["storage_state"] = storage_state
        kwargs["browser_profile"] = BrowserProfile(**profile_kwargs)

        if sensitive_data:
            kwargs["sensitive_data"] = sensitive_data
            kwargs["use_vision"] = False
            if allowed_domains:
                kwargs["allowed_domains"] = allowed_domains
        return Agent(**kwargs)

    return factory
