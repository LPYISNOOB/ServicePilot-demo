from __future__ import annotations

from typing import Any, Callable

from servicepilot.agents.common import AgentDependencies, completed, routed
from servicepilot.llm import extract_requested_amount
from servicepilot.schemas import SupportState


def create_resolution_agent(_: AgentDependencies) -> Callable[[SupportState], dict[str, Any]]:
    def resolution_agent(state: SupportState) -> dict[str, Any]:
        intent = state["intent"]
        order = state.get("order")
        errors = state.get("errors", [])
        action: dict[str, Any] = {"type": "none", "summary": "无需执行外部动作"}
        if "missing_identity" in errors or "identity_mismatch" in errors:
            action = {"type": "request_information", "summary": "请求补充并核验订单信息"}
        elif intent == "refund" and order:
            requested = extract_requested_amount(state["user_message"])
            paid = float(order["total_amount"])
            amount = min(requested if requested is not None else paid, paid)
            action = {
                "type": "create_refund",
                "order_id": order["order_id"],
                "amount": round(amount, 2),
                "reason": state["user_message"][:200],
                "summary": f"创建人民币 {amount:.2f} 元退款申请",
            }
        elif intent == "damaged_goods":
            action = {"type": "request_evidence", "summary": "收集破损和面单照片后继续处理"}
        elif intent == "warranty":
            action = {"type": "request_serial", "summary": "收集序列号并核验质保"}
        elif intent == "complaint" or state["risk_level"] == "high":
            action = {"type": "escalate_to_human", "summary": "升级至人工风险专员"}
        return {
            "proposed_action": action,
            "route_log": routed(state, "resolution_agent"),
            "completed_agents": completed(state, "resolution_agent"),
        }

    return resolution_agent
