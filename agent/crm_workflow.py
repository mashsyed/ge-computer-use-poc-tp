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

"""Visual CRM workflow instruction builder for Gemini Computer Use agent."""

import os
from typing import Dict, Any

def build_crm_instruction(payload: Dict[str, Any]) -> str:
    """Builds explicit step-by-step visual instruction prompt for TP Client CRM case creation.
    
    Args:
        payload: Dictionary containing client_id, email, state, pdf_local_path, tp_client_url, username, password.
    Returns:
        Structured text prompt for the Computer Use agent.
    """
    client_id = payload.get("client_id", "CLI-1001")
    email = payload.get("email", "john.doe@example.com")
    state = payload.get("state", "CA")
    pdf_local_path = payload.get("pdf_local_path", "")
    tp_client_url = payload.get("tp_client_url") or os.environ.get("TP_CLIENT_URL", "http://localhost:8080")
    username = payload.get("username", "admin")
    password = payload.get("password", "password123")

    prompt = f"""You are operating a browser to perform automated tax certificate case creation on the TP Client CRM web application.

Target Web Portal URL: {tp_client_url}
Client ID to Process: {client_id}
Client Email: {email}
Client State Jurisdiction: {state}

Follow these exact visual interaction steps sequentially:

STEP 1: CRM Portal Authentication
- Navigate to the URL: {tp_client_url}
- Locate the "Username / Agent ID" input field (placeholder: "Enter username (e.g. admin)").
- Type "{username}" into the Username field.
- Locate the "Password" input field.
- Type "{password}" into the Password field.
- Click the blue "Sign In to TP Client" button.
- Observe the page update to confirm you are on the "TP Client CRM - Agent Portal" page.

STEP 2: Client Search & Validation
- Locate the search input box (placeholder: "Enter Client ID (e.g., CLI-1001)...").
- Type "{client_id}" into the search box.
- Click the "Search Client" button.
- Verify that the "Client Profile Record" card appears showing Client ID "{client_id}".

STEP 3: Tax Certificate Case Creation
- Scroll down to the "Create New Case" form.
- Verify "Case Category / Type" dropdown is set to "Tax Certificate Request".
- Verify "Tax Year" field is set to "2025".
- In the "Response Message / Dispatch Notes" text area, ensure text includes: "Official Tax Certificate verified for client {client_id} ({state})."
- Click the green "Submit Case & Dispatch Email" button.

STEP 4: Case ID Capture & Completion
- Wait for the page to update and display the green success banner.
- Locate the generated Case ID element inside the yellow highlighted box (e.g., "CASE-2026-XXXXX").
- State the extracted Case ID explicitly in your final text response in the format: "GENERATED_CASE_ID: <Case_ID>".

Guardrails & Errors:
- Observe screen screenshots after each action.
- If any button or input is not immediately visible, scroll down to reveal it.
- Report the final extracted Case ID clearly once captured.
"""
    return prompt
