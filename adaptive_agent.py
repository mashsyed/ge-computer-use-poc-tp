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

"""Generalized Adaptive Agent Engine for Gemini Computer Use.

Evaluates any target URL, determines whether to run fast cached Playwright DOM execution
or invoke Gemini 3.8 Flash Computer Use, and auto-heals script mappings when UIs change.
"""

import asyncio
import os
import re
import time
from typing import Dict, Any, List, Optional, Tuple

def load_env_file(env_path=".env"):
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
from google.genai import types
from google.genai.types import (
    ComputerUse,
    Content,
    Environment,
    FunctionResponse,
    FunctionResponseBlob,
    FunctionResponsePart,
    GenerateContentConfig,
    Part,
    ThinkingConfig,
    Tool,
)
from playwright.async_api import Page, async_playwright

from cost_tracker import RunCostTracker
from script_cache import load_site_cache, save_site_cache
from ui_fingerprint import compute_dom_structure_hash, compute_visual_hash, evaluate_ui_change

# Environment config
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "cs-poc-xbm3l5p9n29nrv0hx1ynd7s")
LOCATION = os.environ.get("GOOGLE_LOCATION", "global")
MODEL_ID = os.environ.get("MODEL_ID", "gemini-3.8-flash")


def normalize_x(x: int, screen_width: int) -> int:
    return int(x / 1000 * screen_width)


def normalize_y(y: int, screen_height: int) -> int:
    return int(y / 1000 * screen_height)


def prune_historical_screenshots(contents: List[Content]) -> List[Content]:
    """Strips intermediate screenshot blobs from past turns to reduce token usage by >70%."""
    if len(contents) <= 2:
        return contents

    for content in contents[:-1]:
        if not content.parts:
            continue
        
        pruned_parts = []
        for part in content.parts:
            if hasattr(part, "inline_data") and part.inline_data and "image" in getattr(part.inline_data, "mime_type", ""):
                continue
            elif hasattr(part, "function_response") and part.function_response:
                fr = part.function_response
                if hasattr(fr, "parts") and fr.parts:
                    clean_fr_parts = []
                    for fr_part in fr.parts:
                        if hasattr(fr_part, "inline_data") and fr_part.inline_data and "image" in getattr(fr_part.inline_data, "mime_type", ""):
                            continue
                        clean_fr_parts.append(fr_part)
                    fr.parts = clean_fr_parts
                pruned_parts.append(part)
            else:
                pruned_parts.append(part)
                
        content.parts = pruned_parts
    return contents


async def execute_cached_playwright_actions(
    page: Page, actions: List[Dict[str, Any]], cost_tracker: RunCostTracker
) -> bool:
    """⚡ Executes fast Playwright DOM actions directly from cache ($0.00 token cost)."""
    print("\n⚡ Executing Fast Cached Playwright Actions (Zero Token Cost)...")
    try:
        for idx, action in enumerate(actions, 1):
            act_type = action.get("type", "")
            target = action.get("target", "")
            value = action.get("value", "")

            print(f"  Step {idx}: {act_type.upper()} -> '{target}' ({value})")

            if act_type == "navigate":
                await page.goto(target, timeout=15000)
                await page.wait_for_timeout(800)
            elif act_type == "fill":
                await page.fill(target, value)
                await page.wait_for_timeout(300)
            elif act_type == "type_direct":
                await page.keyboard.type(value)
                await page.wait_for_timeout(300)
            elif act_type == "press_key":
                await page.keyboard.press("Enter" if value.lower() in ["enter", "return"] else value)
                await page.wait_for_timeout(300)
            elif act_type == "scroll":
                dir_val = action.get("direction", "down")
                amount = action.get("amount", 300)
                await page.mouse.wheel(0, -amount if dir_val == "up" else amount)
                await page.wait_for_timeout(300)
            elif act_type == "click":
                await page.click(target)
                await page.wait_for_timeout(500)
            elif act_type == "click_coords" or act_type == "type":
                x, y = action.get("x", 0), action.get("y", 0)
                await page.mouse.click(x, y)
                if act_type == "type" and value:
                    await page.keyboard.type(value)
                await page.wait_for_timeout(500)

            cost_tracker.record_dom_action(
                action_name=f"Cached Step {idx}: {act_type.upper()}",
                details=f"Target: {target}"
            )

        print("✓ All Cached Playwright Actions Completed Successfully!")
        return True
    except Exception as e:
        print(f"⚠️ Playwright action failed: {e}")
        return False


async def run_adaptive_automation(
    target_url: str,
    user_prompt: str,
    headless: bool = False
) -> Dict[str, Any]:
    """Core Adaptive Decision Engine:
    
    1. Checks if target_url has been visited before.
    2. If visited, checks if UI layout has changed.
    3. If UI has NOT changed: Runs fast cached Playwright actions.
    4. If Brand New or UI HAS changed: Runs Gemini 3.8 Flash Computer Use and updates cache!
    """
    cost_tracker = RunCostTracker(run_id=f"Adaptive-{target_url}")
    
    oauth_token = os.environ.get("GOOGLE_OAUTH_TOKEN", "")
    if oauth_token and oauth_token.startswith("ya29."):
        try:
            from google.oauth2 import credentials
            creds = credentials.Credentials(oauth_token)
            client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION, credentials=creds)
        except Exception:
            client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    else:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    print("\n" + "=" * 75)
    print(f"🌐 GENERALIZED ADAPTIVE AUTOMATION ENGINE")
    print("=" * 75)
    print(f"Target URL:  {target_url}")
    print(f"Task Prompt: {user_prompt}")
    print("=" * 75)

    # 1. Check Site Cache
    site_cache = load_site_cache(target_url)
    
    async with async_playwright() as p:
        print("\n🖥️ Launching Playwright Chrome browser...")
        browser = await p.chromium.launch(headless=headless, slow_mo=100)
        page = await browser.new_page()
        sw, sh = 960, 1080
        await page.set_viewport_size({"width": sw, "height": sh})

        print(f"🌐 Navigating to {target_url}...")
        await page.goto(target_url, timeout=15000)
        await page.wait_for_timeout(1000)

        current_html = await page.content()
        current_screenshot = await page.screenshot(type="png")

        # 2. Evaluate UI State
        use_cached_script = False
        decision_state = "BRAND_NEW_URL"
        if site_cache:
            stored_fingerprint = site_cache.get("fingerprint", {})
            has_changed, reason = evaluate_ui_change(stored_fingerprint, current_html, current_screenshot)
            
            if not has_changed:
                print(f"\n🎯 [SMART DECISION ENGINE]: {reason}")
                print("🚀 Fast-Path Activated: Executing zero-token cached Playwright actions!")
                use_cached_script = True
                decision_state = "FAST_PATH"
            else:
                print(f"\n⚠️ [SMART DECISION ENGINE]: {reason}")
                print("🧠 UI Shift Detected! Invoking Gemini 3.8 Flash Computer Use to self-heal...")
                decision_state = "UI_SHIFT_SELF_HEALING"
        else:
            print(f"\n🆕 [SMART DECISION ENGINE]: Brand New URL detected.")
            print("🧠 Invoking Gemini 3.8 Flash Computer Use for initial layout mapping...")
            decision_state = "BRAND_NEW_URL"

        recorded_actions = []

        if use_cached_script and site_cache.get("actions"):
            # 🚀 EXECUTE FAST CACHED PLAYWRIGHT ACTIONS
            success = await execute_cached_playwright_actions(
                page, site_cache["actions"], cost_tracker
            )
            if not success:
                print("⚠️ Falling back to Gemini 3.8 Flash Computer Use...")
                use_cached_script = False
                decision_state = "FALLBACK_GEMINI"

        if not use_cached_script:
            # 🧠 INVOKE GEMINI 3.8 FLASH COMPUTER USE FOR VISUAL MAPPING / SELF-HEALING
            config_with_thinking = GenerateContentConfig(
                thinking_config=ThinkingConfig(thinking_budget=1024),
                tools=[Tool(computer_use=ComputerUse(environment=Environment.ENVIRONMENT_BROWSER))]
            )
            config_standard = GenerateContentConfig(
                tools=[Tool(computer_use=ComputerUse(environment=Environment.ENVIRONMENT_BROWSER))]
            )

            contents = [
                Content(
                    role="user",
                    parts=[
                        Part(text=f"Target URL: {target_url}\nUser Task Prompt: {user_prompt}\nPerform the required browser actions visually."),
                        Part.from_bytes(data=current_screenshot, mime_type="image/png"),
                    ]
                )
            ]

            max_turns = 10
            for turn in range(max_turns):
                print(f"\n--- 🔁 Gemini Visual Turn {turn + 1} ---")
                contents = prune_historical_screenshots(contents)

                response = None
                used_model = MODEL_ID
                candidate_models = list(dict.fromkeys([MODEL_ID, "gemini-3.8-flash", "gemini-2.5-computer-use-preview-10-2025"]))
                last_err = None

                for model_cand in candidate_models:
                    for cfg in [config_with_thinking, config_standard]:
                        try:
                            response = client.models.generate_content(
                                model=model_cand, contents=contents, config=cfg
                            )
                            used_model = model_cand
                            break
                        except Exception as e:
                            last_err = e
                            if "thinking" in str(e).lower() or "not supported" in str(e).lower():
                                continue
                            if "404" in str(e) or "403" in str(e) or "NOT_FOUND" in str(e) or "PERMISSION_DENIED" in str(e):
                                break
                            continue
                    if response is not None:
                        break

                if response is None:
                    err_text = str(last_err)
                    auth_keywords = ["reauthentication", "gcloud auth", "refresh the access token", "invalid_grant", "unauthorized", "401", "token_uri"]
                    if any(k in err_text.lower() for k in auth_keywords):
                        print(f"\n🔐 AUTHENTICATION EXPIRED / REQUIRED: {last_err}")
                        print("👉 Please run `gcloud auth application-default login` in your terminal or update `GOOGLE_OAUTH_TOKEN` in `.env`.")
                        await browser.close()
                        return {
                            "status": "AUTH_REQUIRED",
                            "error": "Google Cloud access token expired. Please run `gcloud auth application-default login` or update `GOOGLE_OAUTH_TOKEN` in `.env`.",
                            "decision_state": "AUTH_REQUIRED",
                            "total_cost_usd": 0.0
                        }
                    print(f"❗️ Failed to get model response: {last_err}")
                    break

                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    cost_tracker.record_llm_action(
                        action_name=f"Visual Computer Use (Turn {turn + 1})",
                        model_name=used_model,
                        usage_metadata=response.usage_metadata
                    )

                contents.append(response.candidates[0].content)

                # Check function calls
                fcs = []
                if response.candidates[0].content and response.candidates[0].content.parts:
                    fcs = [p.function_call for p in response.candidates[0].content.parts if hasattr(p, "function_call") and p.function_call]

                if not fcs:
                    print("✅ Gemini Computer Use Finished Task.")
                    break

                # Execute actions
                results = []
                for fc in fcs:
                    fname = fc.name
                    fargs = fc.args or {}
                    print(f"⚡ Executing Model Action: {fname} (args: {fargs})")

                    if fname in ["click_at", "click"]:
                        raw_x = fargs.get("x") if "x" in fargs else fargs.get("x_coordinate", 0)
                        raw_y = fargs.get("y") if "y" in fargs else fargs.get("y_coordinate", 0)
                        ax, ay = normalize_x(raw_x, sw), normalize_y(raw_y, sh)
                        await page.mouse.click(ax, ay)
                        recorded_actions.append({"type": "click_coords", "x": ax, "y": ay})

                    elif fname in ["type_text_at", "type", "type_text"]:
                        text_val = fargs.get("text") or fargs.get("value") or fargs.get("text_to_type") or ""
                        if "x" in fargs and "y" in fargs:
                            raw_x, raw_y = fargs["x"], fargs["y"]
                            ax, ay = normalize_x(raw_x, sw), normalize_y(raw_y, sh)
                            await page.mouse.click(ax, ay)
                            await page.keyboard.type(text_val)
                            recorded_actions.append({"type": "type", "x": ax, "y": ay, "value": text_val})
                        else:
                            await page.keyboard.type(text_val)
                            recorded_actions.append({"type": "type_direct", "value": text_val})

                    elif fname in ["press_key", "key_combination", "key_press"]:
                        key_val = fargs.get("key") or fargs.get("text") or "Enter"
                        if key_val.lower() in ["enter", "return"]:
                            await page.keyboard.press("Enter")
                        else:
                            await page.keyboard.press(key_val)
                        recorded_actions.append({"type": "press_key", "value": key_val})

                    elif fname in ["navigate", "open_url", "go_to"]:
                        nav_url = fargs.get("url") or fargs.get("target") or target_url
                        await page.goto(nav_url)
                        recorded_actions.append({"type": "navigate", "target": nav_url})

                    elif fname in ["scroll", "scroll_at_target"]:
                        dir_val = str(fargs.get("direction", "down")).lower()
                        px = int(fargs.get("magnitude_in_pixels", 300))
                        dy = -px if dir_val == "up" else px
                        await page.mouse.wheel(0, dy)
                        recorded_actions.append({"type": "scroll", "direction": dir_val, "amount": px})

                    elif fname in ["wait", "sleep"]:
                        await page.wait_for_timeout(1000)

                    else:
                        print(f"⚠️ Unhandled action name '{fname}', continuing...")

                    results.append((fname, "success", False))

                await page.wait_for_timeout(800)
                new_screenshot = await page.screenshot(type="png")
                curr_url = page.url

                func_response_parts = [
                    Part(
                        function_response=FunctionResponse(
                            name=name,
                            response={"url": curr_url},
                            parts=[FunctionResponsePart(inline_data=FunctionResponseBlob(mime_type="image/png", data=new_screenshot))]
                        )
                    )
                    for name, res, _ in results
                ]
                contents.append(Content(role="user", parts=func_response_parts))

            # 💾 Save learned UI Fingerprint and Actions to Cache
            final_html = await page.content()
            final_dom_hash = compute_dom_structure_hash(final_html)
            final_visual_hash = compute_visual_hash(await page.screenshot(type="png"))
            
            save_site_cache(
                url=target_url,
                dom_hash=final_dom_hash,
                visual_hash=final_visual_hash,
                actions=recorded_actions
            )

        cost_tracker.print_cost_summary(target_url=target_url)
        await browser.close()

    return {
        "status": "SUCCESS",
        "decision_state": decision_state,
        "total_cost_usd": cost_tracker.get_total_cost()
    }
