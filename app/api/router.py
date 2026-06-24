from fastapi import APIRouter

# ── 保留的标准 REST API 路由 ───────────────────────────────
from app.api.routes.health import router as health_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.search import router as search_router
from app.api.routes.task_history import router as task_history_router
from app.api.routes.meal import router as meal_router
from app.api.routes.conversation import router as conversation_router
from app.api.routes.profile import router as profile_router
from app.api.routes.recipe import router as recipe_router

# ── A2A 协议路由（替代旧 agent/agent_tools/mcp） ──────────
from app.a2a.server import router as a2a_router


api_router = APIRouter(prefix="/api")

# ── 标准 REST API ────────────────────────────────────────
api_router.include_router(health_router, tags=["health"])
api_router.include_router(inventory_router, tags=["inventory"])
api_router.include_router(search_router, tags=["search"])
api_router.include_router(task_history_router, tags=["task-history"])
api_router.include_router(meal_router, tags=["meal"])
api_router.include_router(conversation_router, tags=["conversation"])
api_router.include_router(profile_router, tags=["profile"])
api_router.include_router(recipe_router, tags=["recipe"])

# ── A2A 协议（替代旧 /api/agent/*, /api/agents/*, /api/mcp/*） ──
api_router.include_router(a2a_router, tags=["a2a"])
