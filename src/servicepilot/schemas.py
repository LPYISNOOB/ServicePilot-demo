from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


Intent = Literal[
    "refund",
    "logistics",
    "damaged_goods",
    "warranty",
    "order_query",
    "complaint",
    "general",
]
RiskLevel = Literal["low", "medium", "high"]


class Classification(BaseModel):
    intent: Intent = Field(description="工单意图")
    risk_level: RiskLevel = Field(description="风险等级")
    reasoning: str = Field(description="一句话分类依据")


class SupportState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    ticket_id: str
    user_message: str
    customer_email: str
    customer: dict[str, Any] | None
    order_id: str
    order: dict[str, Any] | None
    recent_orders: list[dict[str, Any]]
    identity_verified: bool
    intent: Intent
    risk_level: RiskLevel
    classification_reasoning: str
    evidence: list[dict[str, Any]]
    proposed_action: dict[str, Any]
    requires_approval: bool
    approval_reasons: list[str]
    approval: dict[str, Any]
    action_result: dict[str, Any]
    final_answer: str
    route_log: list[str]
    completed_agents: list[str]
    errors: list[str]
