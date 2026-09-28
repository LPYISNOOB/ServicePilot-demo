from __future__ import annotations

from typing import Any, Callable

from servicepilot.agents.common import AgentDependencies, completed, routed
from servicepilot.schemas import SupportState


def create_policy_agent(dependencies: AgentDependencies) -> Callable[[SupportState], dict[str, Any]]:
    def policy_agent(state: SupportState) -> dict[str, Any]:
        region = (state.get("customer") or {}).get("region", "ALL")
        intent_hints = {
            "refund": "退款 退货 七天无理由 原路退回",
            "logistics": "物流 配送 快递 发货 追踪号 延迟",
            "damaged_goods": "破损 少件 错发 照片 换货",
            "warranty": "质保 保修 维修 序列号",
            "order_query": "订单 身份核验 隐私 邮箱",
            "complaint": "投诉 律师 监管 媒体 安全 升级",
            "general": "售后 客服 政策",
        }
        query = f"{intent_hints[state['intent']]} {state['user_message']}"
        top_k = dependencies.rules.retrieval.top_k
        evidence = [item.as_dict() for item in dependencies.retriever.search(query, k=top_k, region=region)]
        minimum = dependencies.rules.retrieval.minimum_score
        evidence = [item for item in evidence if float(item["score"]) >= minimum]
        return {
            "evidence": evidence,
            "route_log": routed(state, "policy_agent"),
            "completed_agents": completed(state, "policy_agent"),
        }

    return policy_agent
