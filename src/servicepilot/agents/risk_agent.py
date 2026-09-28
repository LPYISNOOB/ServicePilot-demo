from __future__ import annotations

from typing import Any, Callable

from servicepilot.agents.common import AgentDependencies, completed, routed
from servicepilot.database import upsert_ticket
from servicepilot.schemas import SupportState


def create_risk_agent(dependencies: AgentDependencies) -> Callable[[SupportState], dict[str, Any]]:
    def risk_agent(state: SupportState) -> dict[str, Any]:
        action = state["proposed_action"]
        approval_rules = dependencies.rules.approval
        reasons: list[str] = []
        if action.get("type") == "create_refund":
            if approval_rules.require_all_business_writes:
                reasons.append("退款会写入业务数据库")
            if float(action.get("amount", 0)) > approval_rules.refund_amount_threshold:
                reasons.append(f"退款金额超过 {approval_rules.refund_amount_threshold:g} 元")
        if action.get("type") == "grant_compensation" and approval_rules.require_all_compensation:
            reasons.append("任何额外补偿都必须人工审批")
        if state["risk_level"] == "high" and approval_rules.require_high_risk_review:
            reasons.append("命中高风险投诉/安全/法律规则")
        requires_approval = bool(reasons)
        customer_id = (state.get("customer") or {}).get("customer_id")
        upsert_ticket(
            ticket_id=state["ticket_id"],
            user_message=state["user_message"],
            customer_id=customer_id,
            order_id=(state.get("order") or {}).get("order_id"),
            intent=state["intent"],
            risk_level=state["risk_level"],
            status="pending_approval" if requires_approval else "processing",
        )
        return {
            "requires_approval": requires_approval,
            "approval_reasons": reasons,
            "route_log": routed(state, "risk_agent"),
            "completed_agents": completed(state, "risk_agent"),
        }

    return risk_agent

