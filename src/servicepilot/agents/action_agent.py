from __future__ import annotations

from typing import Any, Callable

from servicepilot.agents.common import AgentDependencies, completed, routed
from servicepilot.database import create_refund_request, record_audit, update_ticket_status
from servicepilot.schemas import SupportState


def create_action_agent(_: AgentDependencies) -> Callable[[SupportState], dict[str, Any]]:
    def action_agent(state: SupportState) -> dict[str, Any]:
        action = state["proposed_action"]
        approval = state.get("approval", {})
        result: dict[str, Any] = {"executed": False}
        if state.get("requires_approval") and not approval.get("approved", False):
            result = {"executed": False, "reason": "rejected_by_human"}
        elif action.get("type") == "create_refund":
            refund_id = create_refund_request(
                ticket_id=state["ticket_id"],
                order_id=action["order_id"],
                amount=float(action["amount"]),
                reason=action["reason"],
                approved_by=str(approval.get("reviewer", "policy-engine")),
            )
            result = {"executed": True, "refund_id": refund_id, "amount": float(action["amount"])}
        elif action.get("type") == "escalate_to_human":
            result = {"executed": True, "escalated": True, "queue": "risk_specialist"}
        if result.get("reason") == "rejected_by_human":
            ticket_status = "rejected"
        elif result.get("escalated"):
            ticket_status = "escalated"
        elif action.get("type") in {"request_information", "request_evidence", "request_serial"}:
            ticket_status = "waiting_customer"
        else:
            ticket_status = "resolved"
        update_ticket_status(state["ticket_id"], ticket_status)
        record_audit(
            ticket_id=state["ticket_id"],
            event_type="action_execution",
            actor="agent:action",
            details={"action": action, "result": result, "ticket_status": ticket_status},
        )
        return {
            "action_result": result,
            "route_log": routed(state, "action_agent"),
            "completed_agents": completed(state, "action_agent"),
        }

    return action_agent
