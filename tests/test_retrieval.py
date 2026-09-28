from __future__ import annotations

from servicepilot.retrieval import PolicyRetriever, load_policies


def test_policy_retrieval_filters_inactive_versions() -> None:
    retriever = PolicyRetriever(load_policies())
    evidence = retriever.search("退款 退货 七天无理由", k=5)
    ids = {item.document_id for item in evidence}
    assert "POL-REFUND-001-V2" in ids
    assert "POL-REFUND-001-V1" not in ids


def test_shipping_policy_is_retrievable() -> None:
    evidence = PolicyRetriever().search("物流 配送 快递 追踪号", k=3)
    assert "POL-SHIP-001" in {item.document_id for item in evidence}

