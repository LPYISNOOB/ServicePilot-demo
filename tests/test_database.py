from __future__ import annotations

from pathlib import Path

from servicepilot.database import get_order_for_customer, table_counts


def test_seeded_database_has_expected_shape(seeded_db: Path) -> None:
    counts = table_counts(seeded_db)
    assert counts["customers"] == 100
    assert counts["products"] == 20
    assert counts["orders"] == 500
    assert counts["order_items"] >= 500


def test_order_lookup_requires_matching_owner(seeded_db: Path) -> None:
    owned = get_order_for_customer("SP-2026-0001", "zhangwei@example.com", seeded_db)
    leaked = get_order_for_customer("SP-2026-0001", "customer002@example.com", seeded_db)
    assert owned is not None
    assert owned["customer_id"] == "CUST-0001"
    assert leaked is None

