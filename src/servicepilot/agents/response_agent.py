from __future__ import annotations

from typing import Any, Callable

from langchain_core.messages import AIMessage

from servicepilot.agents.common import AgentDependencies, completed, routed
from servicepilot.database import record_audit
from servicepilot.schemas import SupportState


def create_response_agent(dependencies: AgentDependencies) -> Callable[[SupportState], dict[str, Any]]:
    def response_agent(state: SupportState) -> dict[str, Any]:
        answer = dependencies.language.compose(
            message=state["user_message"],
            intent=state["intent"],
            order=state.get("order"),
            recent_orders=state.get("recent_orders", []),
            evidence=state.get("evidence", []),
            action=state.get("proposed_action", {}),
            approval=state.get("approval", {}),
            result=state.get("action_result", {}),
            errors=state.get("errors", []),
        )
        record_audit(
            ticket_id=state["ticket_id"],
            event_type="response_composed",
            actor="agent:response",
            details={"evidence_ids": [item["document_id"] for item in state.get("evidence", [])]},
        )
        return {
            "final_answer": answer,
            "messages": [AIMessage(content=answer)],
            "route_log": routed(state, "response_agent"),
            "completed_agents": completed(state, "response_agent"),
        }

    return response_agent
