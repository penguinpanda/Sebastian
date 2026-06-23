"""测试 HealthAgentService.analyze_with_history()。"""

from app.schemas.agent_tools import HealthAnalyzeRequest, HealthAnalyzeResponse
from app.services.health_agent_service import HealthAgentService


def test_analyze_without_history() -> None:
    """无饮食历史时返回基础 BMI 分析 + 提示。"""
    payload = HealthAnalyzeRequest(
        user_id="u1",
        height_cm=175,
        weight_kg=70,
    )
    result = HealthAgentService.analyze(payload)
    assert result.bmi == 22.86
    assert result.bmi_category == "normal"
    assert result.suggested_daily_calories == 2000


def test_analyze_with_history_gives_insights() -> None:
    """有饮食历史时返回日均热量和洞察。"""
    payload = HealthAnalyzeRequest(
        user_id="u1",
        height_cm=175,
        weight_kg=70,
    )
    meal_history = [
        {"title": "宫保鸡丁", "calories": 600, "meal_date": "2026-06-10", "confirmed_at": "2026-06-10T12:00:00"},
        {"title": "沙拉", "calories": 300, "meal_date": "2026-06-11", "confirmed_at": "2026-06-11T12:00:00"},
        {"title": "牛排", "calories": 800, "meal_date": "2026-06-12", "confirmed_at": "2026-06-12T12:00:00"},
    ]
    result = HealthAgentService.analyze_with_history(payload, meal_history, days=7)
    # LLM 应生成有意义的建议（长度充足）
    assert len(result.advice) > 30
    # 应包含热量相关信息
    assert "kcal" in result.advice or "千卡" in result.advice or "卡路里" in result.advice
    # 应提及饮食相关建议
    assert "餐" in result.advice or "饮食" in result.advice or "摄入" in result.advice


def test_analyze_with_profile_lose_weight() -> None:
    """减重目标下给出针对性建议。"""
    payload = HealthAnalyzeRequest(
        user_id="u1",
        height_cm=170,
        weight_kg=80,
    )
    meal_history = [
        {"title": "大餐", "calories": 900, "meal_date": "2026-06-12", "confirmed_at": "2026-06-12T12:00:00"},
    ]
    profile = {"health_goal": "lose_weight"}
    result = HealthAgentService.analyze_with_history(payload, meal_history, days=7, user_profile=profile)
    assert "减重" in result.advice or "热量摄入高于" in result.advice


def test_analyze_with_profile_gain_muscle() -> None:
    """增肌目标下给出蛋白质建议。"""
    payload = HealthAnalyzeRequest(
        user_id="u1",
        height_cm=180,
        weight_kg=75,
    )
    meal_history = [
        {"title": "鸡胸饭", "calories": 500, "meal_date": "2026-06-12", "confirmed_at": "2026-06-12T12:00:00"},
    ]
    profile = {"health_goal": "gain_muscle"}
    result = HealthAgentService.analyze_with_history(payload, meal_history, days=7, user_profile=profile)
    assert "增肌" in result.advice
