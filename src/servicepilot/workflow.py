"""Supervisor-led LangGraph multi-agent workflow."""

from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from servicepilot.agents import (
    create_action_agent,
    create_approval_agent,
    create_intent_agent,
    create_order_agent,
    create_policy_agent,
    create_resolution_agent,
    create_response_agent,
    create_risk_agent,
)
from servicepilot.agents.common import AgentDependencies
from servicepilot.business_rules import BusinessRules, load_business_rules
from servicepilot.llm import LanguageService
from servicepilot.retrieval import PolicyRetriever
from servicepilot.schemas import SupportState


AgentDestination = Literal[
    "intent_agent",
    "order_agent",
    "policy_agent",
    "resolution_agent",
    "risk_agent",
    "approval_agent",
    "action_agent",
    "response_agent",
    "__end__",
]


def create_workflow(
    *,
    language_service: LanguageService | None = None,
    rules: BusinessRules | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Build a shared-state supervisor graph with bounded specialist agents.

    The supervisor owns routing. Each specialist owns one tool/domain boundary,
    which keeps database writes, retrieval, risk checks, and language generation
    independently testable.
    """
    active_rules = rules or load_business_rules()
    dependencies = AgentDependencies(
        language=language_service or LanguageService(),
        retriever=PolicyRetriever(),
        rules=active_rules,
    )

    def supervisor(state: SupportState) -> Command[AgentDestination]:
        completed = set(state.get("completed_agents", []))
        if "intent_agent" not in completed:
            destination: AgentDestination = "intent_agent"
        elif "order_agent" not in completed:
            destination = "order_agent"
        elif "policy_agent" not in completed:
            destination = "policy_agent"
        elif "resolution_agent" not in completed:
            destination = "resolution_agent"
        elif "risk_agent" not in completed:
            destination = "risk_agent"
        elif state.get("requires_approval") and "approval_agent" not in completed:
            destination = "approval_agent"
        elif "action_agent" not in completed:
            destination = "action_agent"
        elif "response_agent" not in completed:
            destination = "response_agent"
        else:
            destination = END

        if destination == END:
            return Command(goto=END)
        route = [*state.get("route_log", []), f"supervisor→{destination}"]
        return Command(update={"route_log": route}, goto=destination)

    builder = StateGraph(SupportState)
    builder.add_node("supervisor", supervisor)
    builder.add_node("intent_agent", create_intent_agent(dependencies))
    builder.add_node("order_agent", create_order_agent(dependencies))
    builder.add_node("policy_agent", create_policy_agent(dependencies))
    builder.add_node("resolution_agent", create_resolution_agent(dependencies))
    builder.add_node("risk_agent", create_risk_agent(dependencies))
    builder.add_node("approval_agent", create_approval_agent(dependencies))
    builder.add_node("action_agent", create_action_agent(dependencies))
    builder.add_node("response_agent", create_response_agent(dependencies))
    builder.add_edge(START, "supervisor")
    for node_name in (
        "intent_agent",
        "order_agent",
        "policy_agent",
        "resolution_agent",
        "risk_agent",
        "approval_agent",
        "action_agent",
        "response_agent",
    ):
        builder.add_edge(node_name, "supervisor")
    return builder.compile(checkpointer=checkpointer or InMemorySaver(), name="servicepilot-supervisor")
