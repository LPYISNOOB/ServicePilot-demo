from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from servicepilot.business_rules import BusinessRules
from servicepilot.llm import LanguageService
from servicepilot.retrieval import PolicyRetriever
from servicepilot.schemas import SupportState


@dataclass(slots=True)
class AgentDependencies:
    language: LanguageService
    retriever: PolicyRetriever
    rules: BusinessRules


def last_user_message(state: SupportState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
    raise ValueError("状态中没有用户消息")


def completed(state: SupportState, agent_name: str) -> list[str]:
    return [*state.get("completed_agents", []), agent_name]


def routed(state: SupportState, agent_name: str) -> list[str]:
    return [*state.get("route_log", []), agent_name]

