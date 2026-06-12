from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError as PydanticValidationError

from app.core.errors import LLMError


class InventoryLLMResponse(BaseModel):
    intent: Literal[
        "inventory_query",
        "inventory_adjust",
        "inventory_expiring",
        "inventory_summary",
    ]
    action: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    reply: str = Field(min_length=1, max_length=2000)


def parse_inventory_response(raw: dict[str, Any]) -> InventoryLLMResponse:
    try:
        return InventoryLLMResponse.model_validate(raw)
    except PydanticValidationError as exc:
        raise LLMError(f"LLM response failed schema validation: {exc}") from exc
