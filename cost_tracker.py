# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cost Tracker module for Gemini Computer Use & Hybrid Automation.

Tracks token usage and calculates itemized cost per action for model invocations
and Playwright DOM executions.
"""

from typing import Dict, Any, List, Optional


# Pricing rates per 1,000,000 tokens (USD)
MODEL_PRICING = {
    "gemini-3.8-flash": {
        "input_per_m": 0.10,
        "cached_input_per_m": 0.025,
        "output_per_m": 0.40,
    },
    "gemini-2.0-flash": {
        "input_per_m": 0.10,
        "cached_input_per_m": 0.025,
        "output_per_m": 0.40,
    },
    "gemini-2.5-computer-use-preview-10-2025": {
        "input_per_m": 1.25,
        "cached_input_per_m": 0.3125,
        "output_per_m": 5.00,
    },
    "default": {
        "input_per_m": 0.10,
        "cached_input_per_m": 0.025,
        "output_per_m": 0.40,
    },
}


class ActionCostRecord:
    """Represents the token usage and cost for a single action step."""

    def __init__(
        self,
        action_name: str,
        execution_type: str,  # "LLM_VISION" or "PLAYWRIGHT_DOM"
        model_name: str = "N/A",
        input_tokens: int = 0,
        cached_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ):
        self.action_name = action_name
        self.execution_type = execution_type
        self.model_name = model_name
        self.input_tokens = input_tokens
        self.cached_tokens = cached_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_name": self.action_name,
            "execution_type": self.execution_type,
            "model_name": self.model_name,
            "input_tokens": self.input_tokens,
            "cached_tokens": self.cached_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }


class RunCostTracker:
    """Tracks cumulative and itemized costs across an entire automation run."""

    def __init__(self, run_id: str = "Run-1"):
        self.run_id = run_id
        self.records: List[ActionCostRecord] = []

    def record_dom_action(self, action_name: str, details: str = ""):
        """Records a direct Playwright DOM action ($0.00 token cost)."""
        record = ActionCostRecord(
            action_name=f"{action_name} ({details})" if details else action_name,
            execution_type="PLAYWRIGHT_DOM",
            model_name="N/A (DOM Direct)",
            input_tokens=0,
            cached_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
        self.records.append(record)

    def record_llm_action(
        self, action_name: str, model_name: str, usage_metadata: Any
    ):
        """Calculates exact token cost for a Gemini model invocation."""
        pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["default"])

        input_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
        cached_tokens = (
            getattr(usage_metadata, "cached_content_token_count", 0) or 0
        )
        output_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0

        # Adjust non-cached vs cached input tokens
        non_cached_input = max(0, input_tokens - cached_tokens)

        cost_non_cached_input = (non_cached_input / 1_000_000.0) * pricing[
            "input_per_m"
        ]
        cost_cached_input = (cached_tokens / 1_000_000.0) * pricing[
            "cached_input_per_m"
        ]
        cost_output = (output_tokens / 1_000_000.0) * pricing["output_per_m"]

        total_cost = cost_non_cached_input + cost_cached_input + cost_output

        record = ActionCostRecord(
            action_name=action_name,
            execution_type="LLM_VISION",
            model_name=model_name,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            cost_usd=total_cost,
        )
        self.records.append(record)

    def get_total_cost(self) -> float:
        """Returns total cost in USD."""
        return sum(r.cost_usd for r in self.records)

    def get_total_tokens(self) -> tuple[int, int, int]:
        """Returns total (input_tokens, cached_tokens, output_tokens)."""
        total_in = sum(r.input_tokens for r in self.records)
        total_cached = sum(r.cached_tokens for r in self.records)
        total_out = sum(r.output_tokens for r in self.records)
        return total_in, total_cached, total_out

    def print_cost_summary(self, client_id: str = ""):
        """Prints a clean, formatted itemized cost breakdown table."""
        total_in, total_cached, total_out = self.get_total_tokens()
        total_cost = self.get_total_cost()

        header_title = (
            f"📊 ITEMIZED COST TRACKER BREAKDOWN ({client_id})"
            if client_id
            else "📊 ITEMIZED COST TRACKER BREAKDOWN"
        )
        print("\n" + "=" * 82)
        print(f"{header_title:^82}")
        print("=" * 82)
        print(
            f"{'Step / Action':<26} | {'Type':<14} | {'In Tokens':<9} | {'Out Tokens':<10} | {'Cost (USD)'}"
        )
        print("-" * 82)

        for idx, r in enumerate(self.records, 1):
            short_name = (
                r.action_name[:24] + ".."
                if len(r.action_name) > 26
                else r.action_name
            )
            print(
                f"{idx}. {short_name:<23} | {r.execution_type:<14} | {r.input_tokens:<9} | {r.output_tokens:<10} | ${r.cost_usd:.6f}"
            )

        print("-" * 82)
        print(
            f"{'TOTALS':<26} | {'ALL STEPS':<14} | {total_in:<9} | {total_out:<10} | ${total_cost:.6f}"
        )
        print(
            f"💡 Estimated Cost per 1,000 Runs: ${total_cost * 1000:.2f} USD"
        )
        print("=" * 82 + "\n")
