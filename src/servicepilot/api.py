"""FastAPI delivery layer for the supervisor multi-agent workflow."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from servicepilot.business_rules import load_business_rules
from servicepilot.config import get_settings
from servicepilot.database import get_ticket_audits, table_counts
from servicepilot.paths import FRONTEND_DIR
from servicepilot.service import ServicePilot, interrupt_payload


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    customer_email: str = Field(default="", max_length=320)
    order_id: str = Field(default="", max_length=64)
    thread_id: str | None = None
    ticket_id: str | None = None


class ApprovalRequest(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str = Field(default="", max_length=1000)


class AgentResponse(BaseModel):
    thread_id: str
    ticket_id: str
    status: str
    answer: str = ""
    intent: str = ""
    risk_level: str = ""
    pending_approval: dict[str, Any] | None = None
    route_log: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    action: dict[str, Any] = Field(default_factory=dict)
    action_result: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def get_service() -> ServicePilot:
    return ServicePilot()


def _agent_response(result: dict[str, Any], thread_id: str) -> AgentResponse:
    pending = interrupt_payload(result)
    return AgentResponse(
        thread_id=thread_id,
        ticket_id=str(result.get("ticket_id", "")),
        status="pending_approval" if pending else "completed",
        answer=str(result.get("final_answer", "")),
        intent=str(result.get("intent", "")),
        risk_level=str(result.get("risk_level", "")),
        pending_approval=pending,
        route_log=result.get("route_log", []),
        evidence=result.get("evidence", []),
        action=result.get("proposed_action", {}),
        action_result=result.get("action_result", {}),
        errors=result.get("errors", []),
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ServicePilot API",
        description="Supervisor multi-agent customer support API",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, Any]:
        get_service()
        return {
            "status": "ok",
            "model_mode": settings.model_mode,
            "database": table_counts(),
        }

    @app.get("/api/v1/demo", tags=["system"])
    def demo_identity() -> dict[str, str]:
        return {
            "customer_email": "zhangwei@example.com",
            "order_id": "SP-2026-0001",
            "suggested_message": "这个订单的充电器有问题，我想退款 299 元",
        }

    @app.get("/api/v1/config/public", tags=["system"])
    def public_config() -> dict[str, Any]:
        return {
            "model_mode": settings.model_mode,
            "model_name": settings.model_name or "mock-deterministic",
            "business_rules": load_business_rules().model_dump(),
        }

    @app.post("/api/v1/chat", response_model=AgentResponse, tags=["agent"])
    def chat(request: ChatRequest) -> AgentResponse:
        service = get_service()
        thread_id = request.thread_id or service.new_thread_id()
        try:
            result = service.run(
                request.message,
                customer_email=request.customer_email,
                order_id=request.order_id,
                thread_id=thread_id,
                ticket_id=request.ticket_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _agent_response(result, thread_id)

    @app.post("/api/v1/approvals/{thread_id}", response_model=AgentResponse, tags=["agent"])
    def decide_approval(thread_id: str, request: ApprovalRequest) -> AgentResponse:
        try:
            result = get_service().resume(
                thread_id=thread_id,
                approved=request.approved,
                reviewer=request.reviewer,
                comment=request.comment,
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=404, detail="找不到待审批的会话")
        return _agent_response(result, thread_id)

    @app.get("/api/v1/tickets/{ticket_id}/audits", tags=["audit"])
    def ticket_audits(ticket_id: str) -> dict[str, Any]:
        return {"ticket_id": ticket_id, "events": get_ticket_audits(ticket_id)}

    dist_dir = FRONTEND_DIR / "dist"
    if dist_dir.exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/", include_in_schema=False)
        def frontend_index() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run("servicepilot.api:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
