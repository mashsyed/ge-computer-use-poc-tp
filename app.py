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

"""Main Application Interface for Generalized Adaptive Computer Use.

Usage:
    python app.py --url "http://localhost:8080/login" --prompt "Log into CRM with admin/password123 and submit client CLI-1007"
"""

import argparse
import asyncio
import sys
from adaptive_agent import run_adaptive_automation


async def main():
    parser = argparse.ArgumentParser(description="Gemini Computer Use Generalized Adaptive Automation Engine")
    parser.add_argument("--url", type=str, default="http://localhost:8080/login", help="Target website URL")
    parser.add_argument("--prompt", type=str, default="Log in as admin / password123, search CLI-1007, and submit case.", help="User task prompt")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")

    args = parser.parse_args()

    print("🚀 GEMINI COMPUTER USE GENERALIZED ADAPTIVE PLATFORM")
    print("-" * 65)

    result = await run_adaptive_automation(
        target_url=args.url,
        user_prompt=args.prompt,
        headless=args.headless
    )

    print(f"\n🎉 Execution Completed! Result: {result['status']}")
    print(f"💰 Total Run Cost: ${result['total_cost_usd']:.6f} USD")


if __name__ == "__main__":
    asyncio.run(main())
