from __future__ import annotations

from typing import Any, Callable

from langgraph.types import interrupt

from servicepilot.agents.common import AgentDependencies, completed, routed
from servicepilot.database import record_audit
from servicepilot.schemas import SupportState


def create_approval_agent(_: AgentDependencies) -> Callable[[SupportState], dict[str, Any]]:
    def approval_agent(state: SupportState) -> dict[str, Any]:
        decision = interrupt(
            {
                "type": "servicepilot_approval",
                "ticket_id": state["ticket_id"],
                "risk_level": state["risk_level"],
                "reasons": state["approval_reasons"],
                "proposed_action": state["proposed_action"],
                "order_summary": state.get("order"),
                "evidence": state.get("evidence", []),
            }
        )
        if not isinstance(decision, dict) or "approved" not in decision:
            raise ValueError("恢复审批时必须提供 approved、reviewer 和 comment")
        approval = {
            "approved": bool(decision["approved"]),
            "reviewer": str(decision.get("reviewer") or "anonymous-reviewer"),
            "comment": str(decision.get("comment") or ""),
        }
        record_audit(
            ticket_id=state["ticket_id"],
            event_type="approval_decision",
            actor=f"human:{approval['reviewer']}",
            details=approval,
        )
        return {
            "approval": approval,
            "route_log": routed(state, "approval_agent"),
            "completed_agents": completed(state, "approval_agent"),
        }

    return approval_agent

