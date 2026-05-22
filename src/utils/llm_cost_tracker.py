import os
import json
from typing import Any, Dict
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
import requests

MODEL_PRICING = {
    "deepseek-v4-flash": {
        "input_cache_miss": 0.14,
        "input_cache_hit": 0.0028,
        "output": 0.28,
    },
    "deepseek-v4-pro": {
        "input_cache_miss": 1.74,
        "input_cache_hit": 0.0145,
        "output": 3.48,
    },
}

DEFAULT_MODEL = "deepseek-v4-flash"
USD_TO_CNY = 7.2


class LLMCostTracker(BaseCallbackHandler):
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0
        self.call_details: list[dict] = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if not response.llm_output:
            return
        usage = response.llm_output.get("token_usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        model = response.llm_output.get("model_name", DEFAULT_MODEL)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_calls += 1
        self.call_details.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })

    def get_cost(self, model: str = DEFAULT_MODEL) -> dict:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
        input_cost = self.total_input_tokens / 1_000_000 * pricing["input_cache_miss"]
        output_cost = self.total_output_tokens / 1_000_000 * pricing["output"]
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(input_cost + output_cost, 6),
            "total_cost_cny": round((input_cost + output_cost) * USD_TO_CNY, 6),
        }

    def get_balance(self) -> dict:
        api_key = os.getenv("DEEPSEEK_API")
        if not api_key:
            return {"error": "DEEPSEEK_API not set"}
        try:
            resp = requests.get(
                "https://api.deepseek.com/user/balance",
                headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def report(self, model: str = DEFAULT_MODEL) -> str:
        cost = self.get_cost(model)
        balance = self.get_balance()
        lines = [
            "=" * 50,
            "LLM 调用统计报告",
            "=" * 50,
            f"总调用次数:         {self.total_calls}",
            f"总输入 tokens:      {cost['input_tokens']:,}",
            f"总输出 tokens:      {cost['output_tokens']:,}",
            f"输入费用 (USD):     ${cost['input_cost_usd']}",
            f"输出费用 (USD):     ${cost['output_cost_usd']}",
            f"总费用 (USD):       ${cost['total_cost_usd']}",
            f"总费用 (CNY):       ¥{cost['total_cost_cny']}",
            "-" * 50,
            "账户余额信息:",
        ]
        if "error" in balance:
            lines.append(f"  查询失败: {balance['error']}")
        else:
            balance_iso = balance.get("balance", 0)
            granted = balance.get("granted_balance", 0)
            topped_up = balance.get("topped_up_balance", 0)
            lines.append(f"  总余额 (USD):      ${balance_iso}")
            lines.append(f"  赠送余额 (USD):    ${granted}")
            lines.append(f"  充值余额 (USD):    ${topped_up}")
            lines.append(f"  总余额 (CNY):      ¥{round(balance_iso * USD_TO_CNY, 2)}")
        lines.append("=" * 50)
        return "\n".join(lines)

    def reset(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0
        self.call_details.clear()


_tracker: LLMCostTracker | None = None


def get_tracker() -> LLMCostTracker:
    global _tracker
    if _tracker is None:
        _tracker = LLMCostTracker()
    return _tracker
