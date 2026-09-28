from __future__ import annotations

import uuid
from typing import Any, Callable

from servicepilot.agents.common import AgentDependencies, last_user_message
from servicepilot.database import get_customer_by_email, record_audit
from servicepilot.llm import extract_email, extract_order_id
from servicepilot.schemas import SupportState


def create_intent_agent(dependencies: AgentDependencies) -> Callable[[SupportState], dict[str, Any]]:
    def intent_agent(state: SupportState) -> dict[str, Any]:
        message = last_user_message(state)
        classification = dependencies.language.classify(message)
        email = state.get("customer_email", "").strip() or extract_email(message)
        order_id = state.get("order_id", "").strip().upper() or extract_order_id(message)
        ticket_id = state.get("ticket_id") or f"TKT-{uuid.uuid4().hex[:10].upper()}"
        customer = get_customer_by_email(email) if email else None
        record_audit(
            ticket_id=ticket_id,
            event_type="classified",
            actor="agent:intent",
            details={
                "intent": classification.intent,
                "risk_level": classification.risk_level,
                "reasoning": classification.reasoning,
            },
        )
        return {
            "ticket_id": ticket_id,
            "user_message": message,
            "customer_email": email,
            "customer": customer,
            "order_id": order_id,
            "order": None,
            "recent_orders": [],
            "identity_verified": False,
            "intent": classification.intent,
            "risk_level": classification.risk_level,
            "classification_reasoning": classification.reasoning,
            "evidence": [],
            "proposed_action": {},
            "requires_approval": False,
            "approval_reasons": [],
            "approval": {},
            "action_result": {},
            "final_answer": "",
            "route_log": ["supervisor", "intent_agent"],
            "completed_agents": ["intent_agent"],
            "errors": [],
        }

    return intent_agent

