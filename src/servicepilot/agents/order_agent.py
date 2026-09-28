from __future__ import annotations

from typing import Any, Callable

from servicepilot.agents.common import AgentDependencies, completed, routed
from servicepilot.database import get_order_for_customer, get_recent_orders
from servicepilot.schemas import SupportState


ORDER_INTENTS = {"refund", "logistics", "damaged_goods", "warranty", "order_query"}


def create_order_agent(_: AgentDependencies) -> Callable[[SupportState], dict[str, Any]]:
    def order_agent(state: SupportState) -> dict[str, Any]:
        intent = state["intent"]
        email = state.get("customer_email", "")
        order_id = state.get("order_id", "")
        errors: list[str] = []
        order = None
        recent_orders: list[dict[str, Any]] = []
        verified = False
        if intent in ORDER_INTENTS:
            if not email:
                errors.append("missing_identity")
            elif order_id:
                order = get_order_for_customer(order_id, email)
                verified = order is not None
                if order is None:
                    errors.append("identity_mismatch")
            else:
                recent_orders = get_recent_orders(email)
                verified = bool(state.get("customer"))
                if intent != "order_query":
                    errors.append("missing_identity")
        return {
            "order": order,
            "recent_orders": recent_orders,
            "identity_verified": verified,
            "errors": errors,
            "route_log": routed(state, "order_agent"),
            "completed_agents": completed(state, "order_agent"),
        }

    return order_agent

