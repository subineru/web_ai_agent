"""REST 路由（Adapter）。把 HTTP 轉成 use case 呼叫。"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from application.use_cases.submit_task import SubmitTaskCommand

router = APIRouter()


class CreateTaskBody(BaseModel):
    instruction: str
    start_url: str | None = None
    fields: list[str] | None = None
    handoff_policy: str | None = None  # human_first / ai_then_human / ai_only

    @field_validator("instruction")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("instruction 不可為空白")
        return v


@router.post("/tasks", status_code=202)
async def create_task(body: CreateTaskBody, background: BackgroundTasks, request: Request):
    container = request.app.state.container
    result = container.submit_task().execute(
        SubmitTaskCommand(
            instruction=body.instruction,
            start_url=body.start_url,
            fields=body.fields,
            handoff_policy=body.handoff_policy,
        )
    )
    # 背景執行瀏覽器任務（非同步）
    background.add_task(container.run_browser_job().execute, result.job_id)
    return {"task_id": result.task_id, "job_id": result.job_id}


class SteerBody(BaseModel):
    message: str


class AnswerBody(BaseModel):
    answer: str


class FeedbackBody(BaseModel):
    rating: str
    note: str | None = None


class CredentialsBody(BaseModel):
    site_domain: str
    fields: dict[str, str]  # 例如 {"x_user": "...", "x_pass": "..."}


def _run(use_case_call):
    """把 use case 例外轉成 HTTP 狀態：KeyError→404、ValueError→409。"""
    try:
        use_case_call()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"ok": True}


@router.post("/jobs/{job_id}/steer")
async def steer(job_id: str, body: SteerBody, request: Request):
    c = request.app.state.container
    if getattr(c, "message_store", None) is not None:
        c.message_store.save(job_id, "user", body.message)
    return _run(lambda: c.steer_job().execute(job_id, body.message))


@router.post("/jobs/{job_id}/pause")
async def pause(job_id: str, request: Request):
    c = request.app.state.container
    return _run(lambda: c.pause_job().execute(job_id))


@router.post("/jobs/{job_id}/resume")
async def resume(job_id: str, request: Request):
    c = request.app.state.container
    return _run(lambda: c.resume_job().execute(job_id))


@router.post("/jobs/{job_id}/stop")
async def stop(job_id: str, request: Request):
    c = request.app.state.container
    return _run(lambda: c.stop_job().execute(job_id))


@router.post("/jobs/{job_id}/answer")
async def answer(job_id: str, body: AnswerBody, request: Request):
    c = request.app.state.container
    if getattr(c, "message_store", None) is not None:
        c.message_store.save(job_id, "user", body.answer)
    return _run(lambda: c.answer_clarification().execute(job_id, body.answer))


@router.post("/credentials")
async def credentials(body: CredentialsBody, request: Request):
    """安全提供帳密（依網域）。帳密不寫進日誌/DB，僅供 agent 以 sensitive_data 填表。"""
    c = request.app.state.container
    return _run(lambda: c.provide_credentials().execute(body.site_domain, body.fields))


@router.post("/jobs/{job_id}/feedback")
async def feedback(job_id: str, body: FeedbackBody, request: Request):
    c = request.app.state.container
    return _run(lambda: c.submit_feedback().execute(job_id, rating=body.rating, note=body.note))


@router.post("/jobs/{job_id}/followup", status_code=202)
async def followup(job_id: str, body: SteerBody, background: BackgroundTasks, request: Request):
    """結束後追問：開一個承接前文的新任務並在背景執行。"""
    c = request.app.state.container
    try:
        result = c.follow_up_task().execute(job_id, body.message)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    background.add_task(c.run_browser_job().execute, result.job_id)
    return {"task_id": result.task_id, "job_id": result.job_id}


@router.get("/jobs/{job_id}/export/{fmt}")
async def export_result(job_id: str, fmt: str, request: Request):
    """匯出任務結果：txt / json / csv / xlsx。

    - txt：純文字（永遠可用）
    - json：若結果本身是 JSON 則直接輸出，否則包成 {"result": "..."}
    - csv：若結果是 JSON 陣列的物件，轉成 CSV；否則純文字
    - xlsx：若結果是 JSON 陣列的物件，轉成 Excel；否則 422
    """
    job = request.app.state.container.repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job 不存在")
    if not job.result:
        raise HTTPException(status_code=404, detail="尚無結果可匯出（任務未完成）")

    text = job.result
    short = job_id[:8]

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        parsed = None

    if fmt == "txt":
        return Response(
            content=text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="wagent-{short}.txt"'},
        )

    if fmt == "json":
        out = parsed if parsed is not None else {"result": text}
        return Response(
            content=json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="wagent-{short}.json"'},
        )

    rows = (
        parsed
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict)
        else None
    )

    if fmt == "csv":
        if rows is None:
            # 非陣列格式 → fallback 純文字
            return Response(
                content=text.encode("utf-8"),
                media_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="wagent-{short}.csv"'},
            )
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            content=buf.getvalue().encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="wagent-{short}.csv"'},
        )

    if fmt == "xlsx":
        if rows is None:
            raise HTTPException(status_code=422, detail="結果不是陣列格式，無法匯出 Excel")
        from openpyxl import Workbook  # noqa: PLC0415

        wb = Workbook()
        ws = wb.active
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h, "") for h in headers])
        buf = io.BytesIO()
        wb.save(buf)
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="wagent-{short}.xlsx"'},
        )

    raise HTTPException(status_code=400, detail=f"不支援的格式：{fmt}（可用：txt / json / csv / xlsx）")


@router.get("/jobs/{job_id}/artifacts/{filename}")
async def download_artifact(job_id: str, filename: str):
    """下載瀏覽器任務產生的檔案（PDF、mp3 等）。防路徑穿越：只取純檔名。"""
    safe = Path(filename).name
    path = Path("workspace/downloads") / job_id / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="檔案不存在")
    return FileResponse(str(path), filename=safe)


@router.get("/jobs/{job_id}/messages")
async def get_messages(job_id: str, request: Request):
    """取得任務完整對話歷史（前端對帳的單一真相來源）。"""
    ms = getattr(request.app.state.container, "message_store", None)
    return ms.list_by_job(job_id) if ms is not None else []


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str, request: Request):
    """刪除任務：DB 中訊息、job、task 全清。"""
    c = request.app.state.container
    if getattr(c, "message_store", None) is not None:
        c.message_store.delete_by_job(job_id)
    if hasattr(c.repo, "delete_job"):
        c.repo.delete_job(job_id)
    return Response(status_code=204)


@router.get("/tasks/{job_id}/events")
async def stream_events(job_id: str, request: Request):
    """SSE：即時串流任務事件（status / step / done）。"""
    broker = request.app.state.container.broker

    async def gen():
        async for ev in broker.stream(job_id):
            # 加固：單一事件序列化失敗不得殺掉整條串流（否則尾段全失）。
            try:
                data = json.dumps(ev.data, ensure_ascii=False)
            except (TypeError, ValueError):
                data = json.dumps({"_unserializable": True})
            yield {"event": ev.type, "data": data}

    return EventSourceResponse(gen())


@router.get("/tasks/{job_id}")
async def get_task(job_id: str, request: Request):
    job = request.app.state.container.repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job 不存在")
    return {
        "job_id": job.id,
        "task_id": job.task_id,
        "status": job.status.value,
        "result": job.result,
        "error": job.error,
        "steps": job.steps,
        "wait_reason": job.wait_reason,
    }
