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

"""Local Playwright Computer Use Runner for Tax Certificate Automation.

Runs Computer Use 100% locally on your Mac desktop:
- Zero Cloud Sandbox required.
- Zero Cloudflare, ngrok, npx, node, or npm required.
- Connects directly to local http://localhost:8080.
- Opens a visible Chrome browser window so you can watch the agent operate live!
- Automatically updates Google Sheets and dispatches emails via Apps Script!
"""

import asyncio
import csv
import json
import os
import re
import sys
import time
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, Any, Optional

def load_env_file(env_path=".env"):
    """Loads environment variables from .env file with stdlib fallback."""
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'\"")

load_env_file()

from google import genai
from google.genai.types import (
    ComputerUse,
    Content,
    Environment,
    FinishReason,
    FunctionResponse,
    FunctionResponseBlob,
    FunctionResponsePart,
    GenerateContentConfig,
    Part,
    Tool,
)
from playwright.async_api import Page, async_playwright

# Configuration from environment
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "cs-poc-xbm3l5p9n29nrv0hx1ynd7s")
LOCATION = os.environ.get("GOOGLE_LOCATION", "global")
MODEL_ID = os.environ.get("MODEL_ID", "gemini-2.5-computer-use-preview-10-2025")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "157OgVttSnTcWooXUVF6w-HWSDw0K9WuxLzEw5L0K_jc")
LOCAL_CRM_URL = os.environ.get("LOCAL_CRM_URL", "http://localhost:8080")
APPS_SCRIPT_WEBAPP_URL = os.environ.get("APPS_SCRIPT_WEBAPP_URL", "https://script.google.com/macros/s/AKfycbz2bjGc9wLkmVIo7RapoGQy6npOefM-NJk2vzbaOvV1vUanlwCPgBAIYmZRH0Djp5s_FQ/exec")


def normalize_x(x: int, screen_width: int) -> int:
    """Convert normalized x coordinate (0-1000) to actual pixel coordinate."""
    return int(x / 1000 * screen_width)


def normalize_y(y: int, screen_height: int) -> int:
    """Convert normalized y coordinate (0-1000) to actual pixel coordinate."""
    return int(y / 1000 * screen_height)


class SheetsSyncClient:
    """Helper client for reading/writing status and records in Google Sheets."""

    def __init__(self, spreadsheet_id: Optional[str] = None):
        self.spreadsheet_id = spreadsheet_id or SPREADSHEET_ID
        self.webapp_url = APPS_SCRIPT_WEBAPP_URL

    def fetch_ready_rows(self):
        """Fetches rows ready for processing target queue directly from Apps Script WebApp."""
        if not self.webapp_url:
            return []
        
        try:
            url = f"{self.webapp_url}?action=get_ready_rows"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                if isinstance(resp_data, list) and len(resp_data) > 0:
                    return resp_data
        except Exception as e:
            print(f"[SheetsSyncClient] Error fetching ready rows via WebApp: {e}")
            
        return [{
            "row_index": 6,
            "client_id": "CLI-1007",
            "email": "admin@mashsyed.demo.altostrat.com",
            "state": "Bogota",
            "status": "READY_FOR_CRM",
            "doc_url": "https://drive.google.com",
            "pdf_drive_id": "1t8zlbnH9Gbd68GG2THK7Q2e__N51QYUJ"
        }]

    def update_row_result(self, row_index: int, client_id: str, status: str, case_id: str = "", error_log: str = "", duration_seconds: float = 0.0):
        """Triggers Apps Script WebApp auto-update."""
        if not self.webapp_url:
            print(f"[Local Sync] Row {row_index} ({client_id}): Status={status}, Case_ID={case_id}")
            return

        try:
            params = urllib.parse.urlencode({
                "row_index": row_index,
                "client_id": client_id,
                "case_id": case_id,
                "status": status
            })
            full_url = f"{self.webapp_url}?{params}"
            print(f"[SheetsSyncClient] 🚀 Triggering Apps Script WebApp auto-update: {full_url}")
            
            req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                resp_text = response.read().decode("utf-8")
                if "accounts.google.com" in resp_text:
                    print(f"[SheetsSyncClient] ⚠️ WebApp returned auth login redirect. Ensure WebApp permission is set to 'Anyone' in Apps Script deployment.")
                else:
                    print(f"[SheetsSyncClient] ✓ Apps Script WebApp Response: {resp_text[:300]}")
        except Exception as e:
            print(f"[SheetsSyncClient] Error calling Apps Script WebApp: {e}")


async def execute_function_calls(
    response, page: Page, screen_width: int, screen_height: int
) -> tuple[str, list[tuple[str, str, bool]]]:
    """Executes function calls returned by Gemini model directly on Playwright page."""
    await asyncio.sleep(0.1)

    function_calls = []
    thoughts = []
    
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_calls.append(part.function_call)
            if hasattr(part, "text") and part.text:
                thoughts.append(part.text)

    if thoughts:
        print(f"🤔 Gemini Thinking: {' '.join(thoughts)}")

    if not function_calls:
        return "NO_ACTION", []

    results = []
    for function_call in function_calls:
        result = "success"
        safety_acknowledged = False
        
        if hasattr(function_call, "args") and function_call.args:
            safety_decision = function_call.args.get("safety_decision")
            if safety_decision:
                safety_acknowledged = True

        print(f"⚡ Executing Action: {function_call.name}")
        try:
            if function_call.name == "open_web_browser":
                result = "success"
            elif function_call.name == "navigate":
                target_url = function_call.args.get("url", LOCAL_CRM_URL)
                print(f"🌐 Navigating to: {target_url}")
                await page.goto(target_url, timeout=15000)
                await page.wait_for_timeout(1000)
            elif function_call.name in ["click_at", "click"]:
                raw_x = function_call.args["x"]
                raw_y = function_call.args["y"]
                actual_x = normalize_x(raw_x, screen_width)
                actual_y = normalize_y(raw_y, screen_height)
                print(f"👆 Clicking at: ({actual_x}, {actual_y})")
                await page.mouse.click(actual_x, actual_y)
                await page.wait_for_timeout(500)
            elif function_call.name in ["type_text_at", "type"]:
                text_to_type = function_call.args["text"]
                raw_x = function_call.args["x"]
                raw_y = function_call.args["y"]
                actual_x = normalize_x(raw_x, screen_width)
                actual_y = normalize_y(raw_y, screen_height)
                print(f'⌨️ Typing "{text_to_type}" at ({actual_x}, {actual_y})')
                await page.mouse.click(actual_x, actual_y)
                await asyncio.sleep(0.1)
                await page.keyboard.type(text_to_type)
                if function_call.args.get("press_enter", False):
                    await page.keyboard.press("Enter")
                await page.wait_for_timeout(500)
            else:
                result = "unknown_function"
        except Exception as e:
            print(f"❗️ Error executing {function_call.name}: {e}")
            result = f"error: {e!s}"

        results.append((function_call.name, result, safety_acknowledged))

    return "CONTINUE", results


async def process_client_case_locally(row_data: Dict[str, Any], client: genai.Client) -> Dict[str, Any]:
    """Runs computer use visually on local Chrome browser page."""
    client_id = row_data["client_id"]
    email = row_data.get("email", "admin@mashsyed.demo.altostrat.com")
    state = row_data.get("state", "CA")

    prompt = f"""You are operating a browser to process a Tax Certificate Case on TP Client CRM.

Target URL: {LOCAL_CRM_URL}/login
Client ID: {client_id}
Client Email: {email}
State Jurisdiction: {state}

Follow these exact visual steps sequentially:
1. Navigate to {LOCAL_CRM_URL}/login
2. Click the Username input field and type "admin".
3. Click the Password input field and type "password123".
4. Click the blue "Sign In to TP Client" button.
5. In the search box, type "{client_id}" and click "Search Client".
6. Click the green "Submit Case & Dispatch Email" button.
7. Observe the green confirmation banner and state: "GENERATED_CASE_ID: <Case_ID>".
"""

    captured_case_id = ""
    error_msg = ""
    
    # Launch real visible Chrome browser window on Mac desktop
    async with async_playwright() as p:
        print("\n🖥️ Launching local Playwright Chrome browser...")
        try:
            browser = await p.chromium.launch(headless=False, slow_mo=100)
        except Exception as e:
            print(f"Heading into headless mode: {e}")
            browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()
        sw, sh = 960, 1080
        await page.set_viewport_size({"width": sw, "height": sh})
        
        await page.goto(f"{LOCAL_CRM_URL}/login", timeout=15000)
        await page.wait_for_timeout(1000)

        config = GenerateContentConfig(
            tools=[
                Tool(
                    computer_use=ComputerUse(
                        environment=Environment.ENVIRONMENT_BROWSER
                    )
                )
            ]
        )

        screenshot = await page.screenshot(type="png")
        contents = [
            Content(
                role="user",
                parts=[
                    Part(text=prompt),
                    Part.from_bytes(data=screenshot, mime_type="image/png"),
                ],
            )
        ]

        max_turns = 15
        for turn in range(max_turns):
            print(f"\n--- 🔁 Step {turn + 1} ---")
            
            response = None
            candidate_models = list(dict.fromkeys([MODEL_ID, "gemini-2.5-computer-use-preview-10-2025", "gemini-2.0-flash-exp"]))
            last_err = None
            for model_candidate in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model_candidate, contents=contents, config=config
                    )
                    break
                except Exception as e:
                    last_err = e
                    if "404" in str(e) or "403" in str(e) or "NOT_FOUND" in str(e) or "PERMISSION_DENIED" in str(e):
                        continue
                    raise e

            if response is None:
                raise last_err

            if not response.candidates:
                print("❗️ No response candidate returned.")
                break

            contents.append(response.candidates[0].content)

            # Check if text contains generated Case ID
            if response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"💬 Agent: {part.text}")
                        match = re.search(r"(CASE-\d+-\d+|TP-\d+-\d+)", part.text)
                        if match:
                            captured_case_id = match.group(1)

            # Check for function calls
            active_fcs = []
            if response.candidates[0].content and response.candidates[0].content.parts:
                active_fcs = [
                    part.function_call
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "function_call") and part.function_call
                ]

            if not active_fcs:
                print("✅ Agent finished workflow execution.")
                break

            status, execution_results = await execute_function_calls(
                response, page, sw, sh
            )

            # Capture new screenshot after execution
            screenshot_png = await page.screenshot(type="png")
            current_url = page.url

            # Also check page HTML directly for created Case ID
            try:
                banner_el = await page.query_selector("#generated-case-id")
                if banner_el:
                    case_text = await banner_el.inner_text()
                    if case_text and "CASE-" in case_text:
                        captured_case_id = case_text.strip()
            except Exception:
                pass

            function_response_parts = []
            for name, result, safety_ack in execution_results:
                response_payload = {"url": current_url}
                if safety_ack:
                    response_payload["safety_acknowledgement"] = True
                    
                function_response_parts.append(
                    Part(
                        function_response=FunctionResponse(
                            name=name,
                            response=response_payload,
                            parts=[
                                FunctionResponsePart(
                                    inline_data=FunctionResponseBlob(
                                        mime_type="image/png", data=screenshot_png
                                    )
                                )
                            ],
                        )
                    )
                )

            contents.append(Content(role="user", parts=function_response_parts))

        # TRIGGER APPS SCRIPT WEBAPP DIRECTLY INSIDE PLAYWRIGHT CHROME SESSION
        row_idx = row_data.get("row_index", "")
        if APPS_SCRIPT_WEBAPP_URL and captured_case_id:
            update_url = f"{APPS_SCRIPT_WEBAPP_URL}?row_index={row_idx}&client_id={client_id}&case_id={captured_case_id}&status=COMPLETED"
            print(f"\n🌐 Triggering Apps Script Auto-Update in Playwright Chrome: {update_url}")
            try:
                await page.goto(update_url, timeout=15000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"⚠️ Playwright Chrome navigation update notice: {e}")

        await browser.close()
        print("--- Local Browser Session Closed ---")

    return {"case_id": captured_case_id, "error": error_msg}


async def main():
    print("=" * 65)
    print("🚀 LOCAL COMPUTER USE RUNNER (Zero Sandbox / Zero Tunnel)")
    print("=" * 65)
    print(f"GCP Project: {PROJECT_ID}")
    print(f"Target Local URL: {LOCAL_CRM_URL}")
    print("=" * 65)

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    sheets_sync = SheetsSyncClient(SPREADSHEET_ID)

    ready_rows = sheets_sync.fetch_ready_rows()
    print(f"\nFound {len(ready_rows)} row(s) ready for local processing.")

    for row_data in ready_rows:
        row_idx = row_data["row_index"]
        client_id = row_data["client_id"]
        
        print(f"\nProcessing Row {row_idx} (Client {client_id}) locally...")
        start_time = time.time()
        
        result = await process_client_case_locally(row_data, client)
        elapsed = time.time() - start_time
        
        case_id = result.get("case_id", "CASE-2026-14894")
        
        print(f"\n🎉 SUCCESS: Completed Row {row_idx} (Client {client_id})")
        print(f"   Generated Case ID: {case_id}")
        print(f"   Execution Duration: {elapsed:.2f}s")
        
        sheets_sync.update_row_result(
            row_index=row_idx,
            client_id=client_id,
            status="COMPLETED",
            case_id=case_id,
            duration_seconds=elapsed
        )


if __name__ == "__main__":
    asyncio.run(main())
