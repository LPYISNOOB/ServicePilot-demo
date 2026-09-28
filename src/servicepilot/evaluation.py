"""Offline regression evaluation for routing, approval, privacy, and evidence."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from servicepilot.paths import DATA_DIR, EVAL_DIR, REPORT_DIR
from servicepilot.seed import seed_database
from servicepilot.service import ServicePilot, interrupt_payload


@dataclass(slots=True)
class CaseResult:
    case_id: str
    passed: bool
    intent_ok: bool
    approval_ok: bool
    error_ok: bool
    evidence_ok: bool
    actual_intent: str
    actual_approval: bool
    actual_errors: list[str]
    route: list[str]


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def evaluate_case(service: ServicePilot, case: dict[str, Any]) -> CaseResult:
    thread_id = service.new_thread_id()
    result = service.run(
        case["query"],
        customer_email=case.get("email", ""),
        order_id=case.get("order_id", ""),
        thread_id=thread_id,
    )
    actual_approval = interrupt_payload(result) is not None
    intent_ok = result.get("intent") == case["expected_intent"]
    approval_ok = actual_approval == case["expected_approval"]
    expected_error = case.get("expected_error", "")
    actual_errors = result.get("errors", [])
    error_ok = (not expected_error and not actual_errors) or expected_error in actual_errors
    expected_document = case.get("expected_document", "")
    evidence_ids = {item["document_id"] for item in result.get("evidence", [])}
    evidence_ok = not expected_document or expected_document in evidence_ids

    if actual_approval:
        # 评测不执行真实业务写入；恢复并拒绝，以覆盖审批后的回复路径。
        result = service.resume(
            thread_id=thread_id,
            approved=False,
            reviewer="offline-evaluator",
            comment="离线评测不执行副作用",
        )
    passed = all((intent_ok, approval_ok, error_ok, evidence_ok))
    return CaseResult(
        case_id=case["id"],
        passed=passed,
        intent_ok=intent_ok,
        approval_ok=approval_ok,
        error_ok=error_ok,
        evidence_ok=evidence_ok,
        actual_intent=str(result.get("intent", "")),
        actual_approval=actual_approval,
        actual_errors=actual_errors,
        route=result.get("route_log", []),
    )


def run_evaluation(cases_path: Path | None = None) -> tuple[dict[str, Any], list[CaseResult]]:
    path = cases_path or EVAL_DIR / "cases.jsonl"
    cases = load_cases(path)
    service = ServicePilot()
    results = [evaluate_case(service, case) for case in cases]
    count = len(results)
    summary = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "mode": "offline-deterministic",
        "case_count": count,
        "pass_count": sum(item.passed for item in results),
        "pass_rate": sum(item.passed for item in results) / count if count else 0.0,
        "intent_accuracy": sum(item.intent_ok for item in results) / count if count else 0.0,
        "approval_accuracy": sum(item.approval_ok for item in results) / count if count else 0.0,
        "privacy_error_accuracy": sum(item.error_ok for item in results) / count if count else 0.0,
        "evidence_recall_at_3": sum(item.evidence_ok for item in results) / count if count else 0.0,
    }
    return summary, results


def write_report(summary: dict[str, Any], results: list[CaseResult]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_eval.json"
    md_path = REPORT_DIR / "latest_eval.md"
    json_path.write_text(
        json.dumps({"summary": summary, "cases": [asdict(item) for item in results]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    failed = [item for item in results if not item.passed]
    lines = [
        "# ServicePilot 离线评测报告",
        "",
        f"- 样本数：{summary['case_count']}",
        f"- 通过率：{summary['pass_rate']:.1%}",
        f"- 意图准确率：{summary['intent_accuracy']:.1%}",
        f"- 审批路由准确率：{summary['approval_accuracy']:.1%}",
        f"- 隐私/缺参错误准确率：{summary['privacy_error_accuracy']:.1%}",
        f"- 政策证据 Recall@3：{summary['evidence_recall_at_3']:.1%}",
        "",
        "## 未通过样本",
        "",
    ]
    lines.extend(f"- {item.case_id}: `{item.route}`" for item in failed)
    if not failed:
        lines.append("全部样本通过。")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 ServicePilot 离线评测")
    parser.add_argument("--cases", type=Path, default=None)
    args = parser.parse_args()
    os.environ.setdefault("SERVICEPILOT_DB_PATH", str(DATA_DIR / "evaluation.db"))
    os.environ.setdefault("SERVICEPILOT_CHECKPOINT_PATH", str(DATA_DIR / "evaluation-checkpoints.db"))
    os.environ.setdefault("SERVICEPILOT_MODEL_MODE", "mock")
    seed_database(force=True)
    summary, results = run_evaluation(args.cases)
    json_path, md_path = write_report(summary, results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
