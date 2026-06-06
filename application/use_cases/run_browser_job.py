"""RunBrowserJob use case：驅動 BrowserAgentPort 執行一個 Job，推進狀態機。

只依賴 domain。錯誤的「分級處置」由 RecoverFromError 負責；此處對未預期
例外採最保守處理（標 FAILED 並記錄）。
"""
from __future__ import annotations

import json
from pathlib import Path

from application.use_cases.recover_from_error import RecoverFromError
from domain.compliance import domain_of
from domain.entities import Job
from domain.handoff import HandoffPolicy
from domain.learning import SUCCESS, LearnedTool, augment_instruction
from domain.recovery import ErrorKind
from domain.ports import (
    BrowserAgentPort,
    DomainThrottle,
    JobEventPublisher,
    LearningStore,
    MessageStore,
    SteeringRegistry,
    TaskRepo,
)
from domain.value_objects import AgentStep, JobEvent


class RunBrowserJob:
    def __init__(
        self,
        repo: TaskRepo,
        agent: BrowserAgentPort,
        *,
        max_steps: int = 40,
        publisher: JobEventPublisher | None = None,
        registry: SteeringRegistry | None = None,
        compliance=None,
        throttle: DomainThrottle | None = None,
        learning: LearningStore | None = None,
        default_policy: str = "ai_then_human",
        credentials=None,
        message_store: MessageStore | None = None,
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._max_steps = max_steps
        self._publisher = publisher
        self._registry = registry
        self._compliance = compliance
        self._throttle = throttle
        self._learning = learning
        self._default_policy = default_policy
        self._credentials = credentials
        self._message_store = message_store

    def _emit(self, job_id: str, type_: str, data: dict) -> None:
        # 先持久化再廣播：確保前端收到 done/事件後向 DB 對帳時，資料已寫入。
        self._persist_message(job_id, type_, data)
        if self._publisher is not None:
            self._publisher.publish(job_id, JobEvent(type=type_, data=data))

    def _persist_message(self, job_id: str, type_: str, data: dict) -> None:
        """把對外事件同步存進 MessageStore，作為前端對帳的單一真相來源。"""
        ms = self._message_store
        if ms is None:
            return
        try:
            if type_ == "step":
                ms.save(job_id, "agent", data.get("description"))
            elif type_ == "think":
                ms.save(job_id, "think", None, extra=json.dumps(data, ensure_ascii=False))
            elif type_ == "clarification":
                ms.save(job_id, "agent", data.get("reason"), kind="clarify")
            elif type_ == "reuse":
                ms.save(
                    job_id,
                    "system",
                    f"💡 重用了 {data.get('count')} 條在 {data.get('domain')} 的既有經驗",
                )
            elif type_ == "done":
                artifacts_json = json.dumps(data.get("artifacts", []), ensure_ascii=False)
                if data.get("result"):
                    ms.save(job_id, "agent", data["result"], kind="result", extra=artifacts_json)
                elif data.get("error"):
                    ms.save(job_id, "agent", data["error"], kind="error", extra=artifacts_json)
        except Exception:  # noqa: BLE001 — 持久化失敗不得影響任務執行/SSE
            pass

    async def execute(self, job_id: str) -> Job:
        job = self._repo.get_job(job_id)
        if job is None:
            raise KeyError(f"job 不存在：{job_id}")
        task = self._repo.get_task(job.task_id)
        if task is None:
            raise KeyError(f"task 不存在：{job.task_id}")

        job.start_planning()
        self._repo.update_job(job)

        start_url = task.target_site.url if task.target_site else None

        # 合規關卡：robots.txt + 拒絕清單。被擋下則直接失敗，不啟動 agent。
        if self._compliance is not None:
            decision = await self._compliance.evaluate(start_url)
            for w in decision.warnings:
                self._emit(job.id, "compliance", {"warning": w})
            if not decision.allowed:
                job.fail(error="合規阻擋：" + "；".join(decision.reasons))
                self._repo.update_job(job)
                self._emit(job.id, "done", {"status": job.status.value, "error": job.error})
                return job

        # 禮貌節流：同網域維持最小間隔。
        if self._throttle is not None and start_url:
            await self._throttle.acquire(domain_of(start_url))

        job.start_running()
        self._repo.update_job(job)
        self._emit(job.id, "status", {"status": job.status.value})

        # 重用先前經驗（成功 / 使用者回饋）→ 把指示增強為 few-shot。
        site_domain = domain_of(start_url) if start_url else ""
        instruction = task.instruction
        if self._learning is not None and site_domain:
            tools = self._learning.find_for(site_domain)
            if tools:
                instruction = augment_instruction(task.instruction, tools)
                self._emit(job.id, "reuse", {"count": len(tools), "domain": site_domain})

        def on_step(step: AgentStep) -> None:
            # C1: 有推理資料時先發 think 事件
            if step.thought or step.next_goal:
                self._emit(
                    job.id,
                    "think",
                    {
                        "thought": step.thought,
                        "next_goal": step.next_goal,
                        "evaluation": step.evaluation,
                    },
                )
            job.record_step(step.description)
            self._emit(job.id, "step", {"description": step.description})
            # C2: 偵測到登入頁 → 轉 waiting_for_user + 發 clarification
            if step.login_detected:
                job.wait_for_user(reason=f"瀏覽器停在登入頁：{step.login_url}")
                self._repo.update_job(job)
                self._emit(job.id, "status", {"status": job.status.value})
                self._emit(
                    job.id,
                    "clarification",
                    {
                        "reason": (
                            f"Agent 偵測到登入頁 {step.login_url}。"
                            "請在瀏覽器中完成登入，然後在輸入框送出「已登入」繼續執行。"
                            "（提示：若為 headless 模式，請先在 .env 設 WAGENT_HEADLESS=false）"
                        )
                    },
                )

        control = self._registry.get_or_create(job.id) if self._registry else None

        # 安全帳密：若 vault 有此網域帳密，組成 browser-use sensitive_data（網域綁定）。
        sensitive_data = None
        allowed_domains = None
        if self._credentials is not None and site_domain:
            mapping = self._credentials.get(site_domain)
            if mapping:
                sensitive_data = {f"https://{site_domain}": mapping}
                allowed_domains = [f"https://{site_domain}", f"https://*.{site_domain}"]

        download_dir = Path("workspace/downloads") / job.id
        # 登入 session 持久化備份（user_data_dir）；登入重啟由 gateway 內部處理
        session_dir = Path("workspace/sessions") / job.task_id

        try:
            result = await self._agent.run(
                instruction,
                start_url=start_url,
                max_steps=self._max_steps,
                on_step=on_step,
                control=control,
                sensitive_data=sensitive_data,
                allowed_domains=allowed_domains,
                download_dir=download_dir,
                user_data_dir=session_dir,
            )

        except Exception as exc:  # noqa: BLE001 — 邊界保險，分級由 RecoverFromError 處理
            policy = HandoffPolicy.from_str(task.handoff_policy or self._default_policy)
            decision = RecoverFromError(policy=policy).execute(job, str(exc), attempt=99)
            # 僅 CAPTCHA/登入 才升級人類（人可提供帳密/接力）；其餘錯誤→失敗。
            handoff = decision.action.value == "escalate" and decision.kind in (
                ErrorKind.CAPTCHA,
                ErrorKind.LOGIN,
            )
            if handoff:
                self._repo.update_job(job)  # RecoverFromError 已設 WAITING_FOR_USER
                self._emit(job.id, "status", {"status": job.status.value})
                self._emit(job.id, "clarification", {"reason": decision.reason})
            else:
                if job.status.value != "failed":
                    job.fail(error=str(exc))
                self._repo.update_job(job)
                self._emit(job.id, "done", {"status": job.status.value, "error": job.error})
            return job
        finally:
            if self._registry is not None:
                self._registry.remove(job.id)

        # 若使用者中途按停止，標記失敗（不採用 agent 回傳結果）
        if control is not None and control.stopped:
            job.fail(error="已由使用者停止")
            self._repo.update_job(job)
            self._emit(job.id, "done", {"status": job.status.value, "error": job.error})
            return job

        # C2: 登入接棒由 AnswerClarification 在「另一個 job 實例」上 resume 並寫回 DB，
        # 本執行緒持有的本地 job 不會被更新（仍 stale 停在 WAITING_FOR_USER）。
        # agent.run() 既已返回 = 接棒已結束 → 以 DB 真相判斷是否仍在等待，
        # 不可用 stale 的本地狀態，否則會提早 return、不 succeed、不發 done、不存 result。
        db_job = self._repo.get_job(job.id)
        if db_job is not None and db_job.status.value == "waiting_for_user":
            return job  # DB 也仍在等待（使用者真的沒回覆）→ 保持等待
        if job.status.value == "waiting_for_user":
            # 本地 stale，但 DB 已 resume → 同步回 RUNNING 才能推進到 succeed/fail
            job.resume()

        if result.success:
            job.succeed(result=result.output or "")
            # 沉澱成功經驗，供同網域下次重用。
            if self._learning is not None and site_domain:
                snippet = (result.output or "").strip().replace("\n", " ")[:200]
                guidance = f"先前「{task.instruction}」在此站成功。" + (
                    f"結果樣態：{snippet}" if snippet else ""
                )
                self._learning.save(
                    LearnedTool(site_domain, task.instruction, guidance, SUCCESS)
                )
        else:
            job.fail(error=result.error or "未知錯誤")
        self._repo.update_job(job)
        self._emit(
            job.id,
            "done",
            {
                "status": job.status.value,
                "result": job.result,
                "error": job.error,
                "artifacts": list(result.artifacts),
                "token_stats": result.token_stats,  # B8: token 用量統計
            },
        )
        return job
