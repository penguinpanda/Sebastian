from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ============================================================
# 数据模型定义文件
#
# 功能：
# 定义各个 Agent 服务之间以及 API 接口的数据结构。
#
# 主要包含：
# 1. Recipe Agent（菜谱推荐 Agent）
#    - 接收用户菜谱推荐请求
#    - 返回推荐菜谱结果
#
# 2. Health Agent（健康分析 Agent）
#    - 接收用户身体指标
#    - 返回健康分析结果
#
# 3. Equipment Agent（厨具检查 Agent）
#    - 判断用户已有厨具是否满足菜谱需求
#
# 4. Search Agent（知识检索 Agent）
#    - 接收用户查询
#    - 返回检索结果
#
# 使用：
# Pydantic BaseModel 用于：
# - 请求参数校验
# - 数据类型约束
# - 自动生成 API 文档（如 FastAPI）
#
# ============================================================


# ============================================================
# 菜谱推荐请求模型
#
# 用途：
# Recipe Agent 接收用户生成菜谱请求时使用。
#
# 数据流：
#
# 用户
#  |
# API
#  |
# RecipeRecommendRequest
#  |
# Recipe Agent
#
# ============================================================
class RecipeRecommendRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] = "dinner"
    target_calories: int = Field(default=600, ge=200, le=2000)
    available_equipment: list[str] = Field(default_factory=list)
    dietary_preferences: list[str] = Field(default_factory=list)


# ============================================================
# 仅使用库存材料生成菜谱请求模型
#
# 用途：
# 与 RecipeRecommendRequest 字段一致，但语义上强制
# LLM 仅使用当前库存食材生成菜谱，不得推荐任何库存之外的食材。
#
# ============================================================


class InventoryOnlyRecipeRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] = "dinner"
    target_calories: int = Field(default=600, ge=200, le=2000)
    available_equipment: list[str] = Field(default_factory=list)
    dietary_preferences: list[str] = Field(default_factory=list)



# ============================================================
# 菜谱配料模型
#
# 用于"确认制作 → 扣库存"链路，LLM 生成菜谱时同步产出。
# ============================================================
class RecipeIngredient(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)


# ============================================================
# 菜谱推荐响应模型
#
# 用途：
# Recipe Agent 返回生成结果。
#
# 数据流：
#
# Recipe Agent
#       |
# RecipeRecommendResponse
#       |
# 用户界面
#
# ============================================================
class RecipeRecommendResponse(BaseModel):
    title: str
    rationale: str
    estimated_calories: int
    ingredients: list[RecipeIngredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)

    required_equipment: list[str] = Field(default_factory=list)
    feasible: bool = True

    missing_equipment: list[str] = Field(default_factory=list)
    missing_ingredients: list[str] = Field(default_factory=list)



# ============================================================
# 健康分析请求模型
#
# 用途：
# Health Agent 接收用户身体信息。
#
# 数据流：
#
# 用户身体数据
#       |
# HealthAnalyzeRequest
#       |
# Health Agent
#
# ============================================================
class HealthAnalyzeRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    height_cm: float = Field(gt=50, le=250)
    weight_kg: float = Field(gt=20, le=400)
    target_weight_kg: float | None = Field(default=None, gt=20, le=400)
    daily_calories_taken: int = Field(default=0, ge=0, le=10000)



# ============================================================
# 健康分析响应模型
#
# Health Agent 输出健康评估结果
#
# ============================================================
class HealthAnalyzeResponse(BaseModel):
    bmi: float
    bmi_category: str
    suggested_daily_calories: int
    advice: str



# ============================================================
# 厨具检查请求模型
#
# 用途：
# Equipment Agent 判断：
# 用户已有厨具是否满足菜谱需求。
#
# ============================================================
class EquipmentCheckRequest(BaseModel):
    equipment_owned: list[str] = Field(default_factory=list)
    required_equipment: list[str] = Field(default_factory=list)



# ============================================================
# 厨具检查响应模型
#
# ============================================================
class EquipmentCheckResponse(BaseModel):
    feasible: bool
    missing_equipment: list[str] = Field(default_factory=list)
    suggestion: str



# ============================================================
# 搜索问答请求模型
#
# 用途：
# Search Agent 接收用户知识查询请求。
#
# ============================================================
class SearchAnswerRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1, max_length=300)



# ============================================================
# 搜索问答响应模型
#
# Search Agent 返回检索结果
#
# ============================================================
class SearchAnswerResponse(BaseModel):
    summary: str
    evidence: list[str] = Field(default_factory=list)
    retrieval_mode: Literal["lexical", "vector", "hybrid"] = "hybrid"
