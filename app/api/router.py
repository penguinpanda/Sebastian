from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.health import router as health_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.agent_tools import router as agent_tools_router
from app.api.routes.search import router as search_router
from app.api.routes.task_history import router as task_history_router
from app.api.routes.meal import router as meal_router
from app.api.routes.conversation import router as conversation_router
from app.api.routes.profile import router as profile_router
from app.api.routes.recipe import router as recipe_router


api_router = APIRouter(prefix="/api")
# 所有业务路由都挂在 /api 下，前端只需要配置一个统一的 API_BASE_URL。
api_router.include_router(health_router, tags=["health"])
api_router.include_router(inventory_router, tags=["inventory"])
api_router.include_router(agent_router, tags=["agent"])
api_router.include_router(search_router, tags=["search"])
api_router.include_router(mcp_router, tags=["mcp"])
api_router.include_router(agent_tools_router, tags=["agent-tools"])
api_router.include_router(task_history_router, tags=["task-history"])
api_router.include_router(meal_router, tags=["meal"])
api_router.include_router(conversation_router, tags=["conversation"])
api_router.include_router(profile_router, tags=["profile"])
api_router.include_router(recipe_router, tags=["recipe"])
