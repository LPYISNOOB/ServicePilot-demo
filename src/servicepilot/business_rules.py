"""Validated, reloadable business parameters stored outside Python code."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from servicepilot.paths import CONFIG_DIR


class ApprovalRules(BaseModel):
    refund_amount_threshold: float = Field(default=200.0, ge=0)
    require_all_business_writes: bool = True
    require_all_compensation: bool = True
    require_high_risk_review: bool = True


class RiskRules(BaseModel):
    high_keywords: list[str]
    medium_intents: list[str]


class RetrievalRules(BaseModel):
    top_k: int = Field(default=3, ge=1, le=20)
    minimum_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    active_documents_only: bool = True


class DemoDataRules(BaseModel):
    random_seed: int = 42
    customer_count: int = Field(default=100, ge=10, le=10000)
    order_count: int = Field(default=500, ge=10, le=100000)


class BusinessRules(BaseModel):
    approval: ApprovalRules
    risk: RiskRules
    retrieval: RetrievalRules
    demo_data: DemoDataRules


@lru_cache(maxsize=4)
def load_business_rules(path: str | Path | None = None) -> BusinessRules:
    config_path = Path(path or CONFIG_DIR / "business_rules.json").resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        return BusinessRules.model_validate(json.load(handle))


def reload_business_rules(path: str | Path | None = None) -> BusinessRules:
    load_business_rules.cache_clear()
    return load_business_rules(path)
