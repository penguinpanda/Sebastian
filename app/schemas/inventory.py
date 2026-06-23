from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ============================================================
# 库存创建请求模型
# 用于新增库存物品时接收前端传递的数据
#
# 例如：
# {
#     "name": "鸡胸肉",
#     "quantity": 500,
#     "unit": "g",
#     "expire_date": "2026-06-20",
#     "note": "冷藏保存"
# }
# ============================================================

class InventoryCreate(BaseModel):
    user_id: str = Field(default="default", min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    expire_date: date
    note: str | None = Field(default=None, max_length=500)

# ============================================================
# 库存调整请求模型
# 用于修改已有库存数量
#
# 例如：
# 增加库存：
# {
#     "delta": 200,
#     "note": "购买补充"
# }
#
# 减少库存：
# {
#     "delta": -100,
#     "note": "制作菜品消耗"
# }
# ============================================================
class InventoryAdjust(BaseModel):
    delta: float
    note: str | None = Field(default=None, max_length=500)



# ============================================================
# 库存查询返回模型
# 用于向前端返回完整库存信息
#
# 对应数据库中的库存记录
# ============================================================
class InventoryRead(BaseModel):
    id: UUID
    user_id: str
    name: str
    quantity: float
    unit: str
    expire_date: date
    note: str | None
    created_at: datetime
    updated_at: datetime



# ============================================================
# 即将过期库存模型
#
# 用于提醒用户哪些食材即将过期
#
# 例如：
# 鸡蛋:
# 剩余3天过期
# ============================================================
class ExpiringInventoryItem(BaseModel):
    id: UUID
    name: str
    quantity: float
    unit: str
    expire_date: date
    days_left: int



# ============================================================
# 库存统计信息模型
#
# 用于返回库存整体情况
# ============================================================
class InventorySummary(BaseModel):
    total_items: int
    expiring_soon: int
