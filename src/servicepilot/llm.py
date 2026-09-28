"""Model boundary: business rules stay deterministic; language work is replaceable."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from servicepilot.config import Settings, get_settings
from servicepilot.business_rules import BusinessRules, load_business_rules
from servicepilot.schemas import Classification


def heuristic_classify(message: str, rules: BusinessRules | None = None) -> Classification:
    active_rules = rules or load_business_rules()
    text = message.lower()
    if any(term in text for term in ("退款", "退货", "退钱")):
        intent = "refund"
    elif any(term in text for term in ("破损", "坏了", "少件", "错发", "碎了")):
        intent = "damaged_goods"
    elif any(term in text for term in ("物流", "快递", "配送", "到哪", "发货", "没收到", "没有收到", "追踪")):
        intent = "logistics"
    elif any(term in text for term in ("质保", "保修", "维修", "售后期")):
        intent = "warranty"
    elif any(term in text for term in ("投诉", "差评", "律师", "监管", "曝光")):
        intent = "complaint"
    elif any(term in text for term in ("订单", "购买记录", "买了什么")):
        intent = "order_query"
    else:
        intent = "general"

    if any(term in text for term in active_rules.risk.high_keywords):
        risk = "high"
        reason = "命中法律、安全或舆情升级关键词"
    elif intent in set(active_rules.risk.medium_intents):
        risk = "medium"
        reason = "涉及资金、商品质量、投诉或质保"
    else:
        risk = "low"
        reason = "只涉及一般咨询或只读查询"
    return Classification(intent=intent, risk_level=risk, reasoning=reason)


class LanguageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.rules = load_business_rules()
        self._model: ChatOpenAI | None = None

    @property
    def model(self) -> ChatOpenAI:
        if self._model is None:
            self.settings.validate_model()
            kwargs: dict[str, Any] = {
                "model": self.settings.model_name,
                "api_key": self.settings.api_key,
                "temperature": self.settings.temperature,
                "max_retries": 2,
                "timeout": 45,
            }
            if self.settings.base_url:
                kwargs["base_url"] = self.settings.base_url
            self._model = ChatOpenAI(**kwargs)
        return self._model

    def classify(self, message: str) -> Classification:
        deterministic = heuristic_classify(message, self.rules)
        if not self.settings.uses_real_model:
            return deterministic
        # 兼容 DeepSeek 等不支持 json_schema / tool_choice 的 OpenAI 兼容接口：
        # 使用普通文本调用 + JSON prompt，解析失败时回退确定性规则，保证流程不中断。
        try:
            response = self.model.invoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是企业售后工单分类器。只判断意图和初始风险。"
                            "法律威胁、监管投诉、媒体曝光、人身或用电安全必须为 high。"
                            "只输出一个 JSON 对象，不要输出任何其他文字，格式："
                            '{"intent": "refund|logistics|damaged_goods|warranty|order_query|complaint|general", '
                            '"risk_level": "low|medium|high", "reasoning": "一句话依据"}'
                        ),
                    },
                    {"role": "user", "content": message},
                ]
            )
            model_result = Classification.model_validate_json(_extract_json(str(response.content)))
        except Exception:
            # 模型输出不合规（如枚举值非英文）时回退确定性规则
            model_result = deterministic
        # 硬规则只允许提高风险，不允许模型将高风险降级。
        if deterministic.risk_level == "high":
            model_result.risk_level = "high"
            model_result.reasoning = f"{model_result.reasoning}；硬规则命中高风险关键词"
        return model_result

    def compose(
        self,
        *,
        message: str,
        intent: str,
        order: dict[str, Any] | None,
        recent_orders: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        action: dict[str, Any],
        approval: dict[str, Any],
        result: dict[str, Any],
        errors: list[str],
    ) -> str:
        if not self.settings.uses_real_model:
            return mock_compose(
                intent=intent,
                order=order,
                recent_orders=recent_orders,
                evidence=evidence,
                action=action,
                approval=approval,
                result=result,
                errors=errors,
            )
        payload = {
            "客户问题": message,
            "意图": intent,
            "已核验订单": order,
            "最近订单": recent_orders,
            "政策证据": evidence,
            "建议动作": action,
            "人工审批": approval,
            "执行结果": result,
            "错误": errors,
        }
        response = self.model.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "你是 ServicePilot 客服回复生成器。只能使用给定事实；不得编造。"
                        "身份核验失败时不得泄露订单是否存在。退款未获批准时不得声称已退款。"
                        "先直接回答，再说明下一步；最后用“依据：”列出政策标题、版本和源文件。"
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ]
        )
        return str(response.content)


def _extract_json(text: str) -> str:
    """从模型输出中提取 JSON 对象文本（容忍代码块围栏与前后缀文字）。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"未找到 JSON 对象：{text[:200]}")
    return text[start : end + 1]


def _citations(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return ""
    citations = "、".join(
        f"《{item['title']}》v{item['version']}（{item['source']}）" for item in evidence[:3]
    )
    return f"\n\n依据：{citations}"


def mock_compose(
    *,
    intent: str,
    order: dict[str, Any] | None,
    recent_orders: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    action: dict[str, Any],
    approval: dict[str, Any],
    result: dict[str, Any],
    errors: list[str],
) -> str:
    if "identity_mismatch" in errors:
        answer = "未找到与当前邮箱匹配的订单。请检查邮箱和订单号后重试；为保护隐私，我不能透露其他订单信息。"
    elif "missing_identity" in errors:
        answer = "处理这个问题需要先核验身份。请同时提供下单邮箱和订单号。"
    elif approval and not approval.get("approved", False):
        answer = f"你的诉求已经记录，但建议操作未获人工批准，因此没有执行。审核备注：{approval.get('comment') or '未提供'}。"
    elif result.get("refund_id"):
        answer = (
            f"退款申请已由人工批准并登记，编号为 {result['refund_id']}，"
            f"金额人民币 {result['amount']:.2f} 元。款项将按政策原路退回。"
        )
    elif action.get("type") == "request_evidence":
        answer = "我已记录破损问题。请补充破损部位、快递面单照片和商品序列号；确认后可继续换货或退款流程。"
    elif action.get("type") == "request_serial":
        answer = "请提供商品序列号和故障现象，我会据此核对质保范围并安排下一步。"
    elif result.get("escalated"):
        answer = "你的诉求已记录并转交人工专员。当前不会自动承诺赔偿或作出责任认定，专员将进一步核查。"
    elif order and intent == "logistics":
        tracking = order.get("tracking_no") or "尚未生成"
        answer = f"订单 {order['order_id']} 当前状态为 {order['status']}，物流单号：{tracking}。"
    elif order and intent == "order_query":
        answer = f"订单 {order['order_id']} 当前状态为 {order['status']}，实付金额人民币 {order['total_amount']:.2f} 元。"
    elif recent_orders:
        lines = [f"- {item['order_id']}：{item['status']}，人民币 {item['total_amount']:.2f} 元" for item in recent_orders]
        answer = "已核验到最近订单：\n" + "\n".join(lines)
    elif intent == "general":
        answer = "我可以协助查询订单、物流、退货退款、到货破损和质保问题。涉及具体订单时，请提供下单邮箱和订单号。"
    else:
        answer = "我已记录你的问题。请补充订单号、下单邮箱以及必要的商品或物流信息，以便继续处理。"
    return answer + _citations(evidence)


def extract_order_id(message: str) -> str:
    match = re.search(r"\bSP-\d{4}-\d{4}\b", message, flags=re.IGNORECASE)
    return match.group(0).upper() if match else ""


def extract_email(message: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", message, flags=re.IGNORECASE)
    return match.group(0).lower() if match else ""


def extract_requested_amount(message: str) -> float | None:
    patterns = [r"退款\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)", r"[¥￥]\s*(\d+(?:\.\d{1,2})?)"]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return float(match.group(1))
    return None
