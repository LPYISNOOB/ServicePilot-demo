from __future__ import annotations

from pathlib import Path

from servicepilot.database import get_ticket, table_counts
from servicepilot.service import ServicePilot, interrupt_payload


def test_read_only_order_query_completes_without_approval(seeded_db: Path) -> None:
    service = ServicePilot()
    result = service.run(
        "查询这个订单的物流状态",
        customer_email="zhangwei@example.com",
        order_id="SP-2026-0001",
    )
    assert result["intent"] == "logistics"
    assert interrupt_payload(result) is None
    assert "SF" in result["final_answer"]
    assert result["completed_agents"][-1] == "response_agent"
    assert get_ticket(result["ticket_id"], seeded_db)["status"] == "resolved"


def test_refund_pauses_then_rejection_has_no_business_write(seeded_db: Path) -> None:
    service = ServicePilot()
    thread_id = service.new_thread_id()
    pending = service.run(
        "我想退款 299 元",
        customer_email="zhangwei@example.com",
        order_id="SP-2026-0001",
        thread_id=thread_id,
    )
    assert interrupt_payload(pending) is not None
    assert "approval_agent" not in pending["completed_agents"]

    completed = service.resume(
        thread_id=thread_id,
        approved=False,
        reviewer="pytest-reviewer",
        comment="证据不足",
    )
    assert completed["action_result"]["reason"] == "rejected_by_human"
    assert table_counts(seeded_db)["refund_requests"] == 0
    assert get_ticket(completed["ticket_id"], seeded_db)["status"] == "rejected"


def test_approved_refund_writes_once(seeded_db: Path) -> None:
    service = ServicePilot()
    thread_id = service.new_thread_id()
    pending = service.run(
        "充电器有质量问题，退款 299 元",
        customer_email="zhangwei@example.com",
        order_id="SP-2026-0001",
        thread_id=thread_id,
    )
    assert interrupt_payload(pending) is not None
    completed = service.resume(
        thread_id=thread_id,
        approved=True,
        reviewer="pytest-reviewer",
        comment="批准测试退款",
    )
    assert completed["action_result"]["refund_id"].startswith("RF-")
    assert table_counts(seeded_db)["refund_requests"] == 1
    assert get_ticket(completed["ticket_id"], seeded_db)["status"] == "resolved"


def test_identity_mismatch_does_not_disclose_order(seeded_db: Path) -> None:
    result = ServicePilot().run(
        "查询这个订单",
        customer_email="customer002@example.com",
        order_id="SP-2026-0001",
    )
    assert "identity_mismatch" in result["errors"]
    assert result["order"] is None
    assert "为保护隐私" in result["final_answer"]


def test_pending_approval_survives_service_recreation(seeded_db: Path) -> None:
    first_process = ServicePilot()
    thread_id = first_process.new_thread_id()
    pending = first_process.run(
        "我要退款 299 元",
        customer_email="zhangwei@example.com",
        order_id="SP-2026-0001",
        thread_id=thread_id,
    )
    assert interrupt_payload(pending) is not None

    recreated_process = ServicePilot()
    completed = recreated_process.resume(
        thread_id=thread_id,
        approved=False,
        reviewer="restart-test",
        comment="验证重启恢复",
    )
    assert completed["action_result"]["reason"] == "rejected_by_human"
    assert completed["completed_agents"][-1] == "response_agent"
