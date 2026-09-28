from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from servicepilot.api import create_app, get_service
from servicepilot.paths import FRONTEND_DIR
import pytest


def test_chat_and_approval_api(seeded_db: Path) -> None:
    get_service.cache_clear()
    client = TestClient(create_app())
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["database"]["customers"] == 100

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "我想退款 299 元",
            "customer_email": "zhangwei@example.com",
            "order_id": "SP-2026-0001",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["pending_approval"]["proposed_action"]["type"] == "create_refund"

    decision = client.post(
        f"/api/v1/approvals/{body['thread_id']}",
        json={"approved": False, "reviewer": "api-tester", "comment": "拒绝副作用"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "completed"
    assert decision.json()["action_result"]["reason"] == "rejected_by_human"


def test_public_config_contains_adjustable_rules(seeded_db: Path) -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/config/public")
    assert response.status_code == 200
    assert response.json()["business_rules"]["approval"]["refund_amount_threshold"] == 200.0


def test_built_react_app_is_served_by_fastapi(seeded_db: Path) -> None:
    if not (FRONTEND_DIR / "dist" / "index.html").exists():
        pytest.skip("先执行 npm run build 才会生成 React dist")
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "ServicePilot" in response.text
