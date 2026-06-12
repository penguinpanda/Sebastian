from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.models.agent import AgentTask, ToolCallLog
from app.orchestration.graph import run_inventory_agent
from app.services.agent_rate_limiter import check_agent_rate_limit
from app.services.agent_task_cache import get_agent_task_status, set_agent_task_status
from app.services.agent_task_queue import enqueue_agent_task, get_agent_queue_size

router = APIRouter(prefix="/agent")


class ChatRequest(BaseModel):
    """前端聊天入口：message 是用户原文，user_id 用于限流、审计和任务归属。"""

    message: str
    user_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    user_id: str | None = None
    detail: dict = Field(default_factory=dict)
    source: str


class QueueStatsResponse(BaseModel):
    queue_size: int


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db_session)) -> ChatResponse:
    """创建 AgentTask 记录，同步运行库存 Agent，并写入工具调用日志。"""
    trace_id = getattr(request.state, "trace_id", None)
    request.state.user_id = payload.user_id
    request.state.action = "chat"
    rate_user = payload.user_id or "anonymous"
    if not check_agent_rate_limit(rate_user):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    task = AgentTask(
        id=uuid4(),
        user_id=payload.user_id,
        task_type="inventory_chat",
        status="running",
        input_payload={"message": payload.message},
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    db.flush()
    # 队列和缓存用于“任务状态查询”体验；当前实现仍在请求内同步得到 reply。
    enqueue_agent_task(str(task.id), payload.user_id, payload.message)
    set_agent_task_status(
        str(task.id),
        "running",
        user_id=payload.user_id,
        detail={"message": payload.message},
    )

    t0 = datetime.now(timezone.utc)
    error_detail: str | None = None
    reply = ""

    try:
        reply = run_inventory_agent(payload.message, user_id=payload.user_id)
        task.status = "completed"
        task.output_payload = {"reply": reply}
        set_agent_task_status(
            str(task.id),
            "completed",
            user_id=payload.user_id,
            detail={"reply": reply},
        )
    except Exception as exc:
        # 失败也落库，调用方拿到 task_id 后仍能查询到失败原因。
        error_detail = str(exc)
        reply = "Something went wrong. Please try again."
        task.status = "failed"
        task.output_payload = {"error": error_detail}
        set_agent_task_status(
            str(task.id),
            "failed",
            user_id=payload.user_id,
            detail={"error": error_detail},
        )

    latency_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    log = ToolCallLog(
        id=uuid4(),
        task_id=task.id,
        trace_id=trace_id,
        tool_name="inventory_agent_graph",
        latency_ms=latency_ms,
        result_status="ok" if not error_detail else "error",
        error_detail=error_detail,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()

    return ChatResponse(reply=reply, task_id=str(task.id))


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str, db: Session = Depends(get_db_session)) -> TaskStatusResponse:
    """优先从 Redis 状态缓存读取，缓存失效后回退到数据库任务表。"""
    cached = get_agent_task_status(task_id)
    if cached:
        return TaskStatusResponse(
            task_id=task_id,
            status=str(cached.get("status", "unknown")),
            user_id=cached.get("user_id"),
            detail=cached.get("detail") or {},
            source="cache",
        )

    try:
        task_uuid = UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid task_id format") from exc

    task = db.scalar(select(AgentTask).where(AgentTask.id == task_uuid))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task_id,
        status=task.status,
        user_id=task.user_id,
        detail=task.output_payload or task.input_payload or {},
        source="database",
    )


@router.get("/queue/stats", response_model=QueueStatsResponse)
def get_queue_stats() -> QueueStatsResponse:
    return QueueStatsResponse(queue_size=get_agent_queue_size())
