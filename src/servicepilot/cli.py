from __future__ import annotations

import argparse
import json

from servicepilot.service import ServicePilot, interrupt_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="ServicePilot 命令行演示")
    parser.add_argument("--message", required=True, help="客户问题")
    parser.add_argument("--email", default="", help="下单邮箱")
    parser.add_argument("--order-id", default="", help="订单号")
    parser.add_argument("--reviewer", default="cli-reviewer", help="审批人")
    parser.add_argument("--auto-reject", action="store_true", help="遇到审批时直接拒绝，适合自动脚本")
    args = parser.parse_args()

    service = ServicePilot()
    thread_id = service.new_thread_id()
    result = service.run(
        args.message,
        customer_email=args.email,
        order_id=args.order_id,
        thread_id=thread_id,
    )
    pending = interrupt_payload(result)
    if pending:
        print("\n=== 等待人工审批 ===")
        print(json.dumps(pending, ensure_ascii=False, indent=2, default=str))
        approved = False
        comment = "CLI 自动拒绝"
        if not args.auto_reject:
            approved = input("是否批准？[y/N] ").strip().lower() in {"y", "yes"}
            comment = input("审批备注（可留空）：").strip()
        result = service.resume(
            thread_id=thread_id,
            approved=approved,
            reviewer=args.reviewer,
            comment=comment,
        )

    print("\n=== 客服回复 ===")
    print(result.get("final_answer", "流程尚未生成回复"))
    print("\n=== Agent 轨迹 ===")
    print(" -> ".join(result.get("route_log", [])))
    print(f"Ticket: {result.get('ticket_id', 'unknown')}")


if __name__ == "__main__":
    main()

