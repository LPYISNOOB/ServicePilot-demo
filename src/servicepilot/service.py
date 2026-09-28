"""Application facade shared by FastAPI, CLI, tests, and evaluation."""

from __future__ import annotations

import uuid
import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from servicepilot.config import get_settings
from servicepilot.seed import seed_database
from servicepilot.workflow import create_workflow


class ServicePilot:
    def __init__(self) -> None:
        seed_database()
        settings = get_settings()
        self._checkpoint_connection: sqlite3.Connection | None = None
        if settings.checkpoint_mode == "memory":
            checkpointer = InMemorySaver()
        elif settings.checkpoint_mode == "sqlite":
            checkpoint_path = Path(settings.checkpoint_path).expanduser().resolve()
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self._checkpoint_connection = sqlite3.connect(
                checkpoint_path,
                check_same_thread=False,
                timeout=30,
            )
            checkpointer = SqliteSaver(self._checkpoint_connection)
        else:
            raise ValueError("SERVICEPILOT_CHECKPOINT_MODE 只支持 sqlite 或 memory")
        self.graph = create_workflow(checkpointer=checkpointer)

    @staticmethod
    def new_thread_id() -> str:
        return f"thread-{uuid.uuid4().hex}"

    @staticmethod
    def new_ticket_id() -> str:
        return f"TKT-{uuid.uuid4().hex[:10].upper()}"

    def run(
        self,
        message: str,
        *,
        customer_email: str = "",
        order_id: str = "",
        thread_id: str | None = None,
        ticket_id: str | None = None,
    ) -> dict[str, Any]:
        if not message.strip():
            raise ValueError("客户问题不能为空")
        active_thread_id = thread_id or self.new_thread_id()
        active_ticket_id = ticket_id or self.new_ticket_id()
        config = {
            "configurable": {"thread_id": active_thread_id},
            "run_name": "servicepilot-ticket",
            "tags": ["servicepilot", "supervisor-multi-agent"],
            "metadata": {"ticket_id": active_ticket_id},
        }
        return self.graph.invoke(
            {
                "messages": [HumanMessage(content=message.strip())],
                "customer_email": customer_email.strip(),
                "order_id": order_id.strip().upper(),
                "ticket_id": active_ticket_id,
                "completed_agents": [],
                "route_log": [],
                "errors": [],
            },
            config=config,
        )

    def resume(
        self,
        *,
        thread_id: str,
        approved: bool,
        reviewer: str,
        comment: str = "",
    ) -> dict[str, Any]:
        config = {
            "configurable": {"thread_id": thread_id},
            "run_name": "servicepilot-approval-resume",
            "tags": ["servicepilot", "human-in-the-loop"],
        }
        return self.graph.invoke(
            Command(
                resume={
                    "approved": approved,
                    "reviewer": reviewer.strip() or "anonymous-reviewer",
                    "comment": comment.strip(),
                }
            ),
            config=config,
        )


def interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__", ())
    if not interrupts:
        return None
    first = interrupts[0]
    return first.value if hasattr(first, "value") else first
