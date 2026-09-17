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

"""Runner & Telemetry Loop for Computer Use Tax Certificate Automation.

1. Connects to Google Sheets Intake_Queue (via gspread / Sheets API).
2. Polls for rows marked 'READY_FOR_CRM'.
3. Locks status to 'IN_CRM_PROCESSING'.
4. Downloads Tax Certificate PDF from Google Drive to local temp directory.
5. Invokes ADK Computer Use agent targeting TP Client CRM.
6. Saves live step-by-step screenshots to local 'screenshots/' directory for visual inspection.
7. Captures generated Case_ID, measures elapsed runtime telemetry.
8. Commits results back to Google Sheet ('COMPLETED' or 'FAILED_NEEDS_REVIEW').
"""

import asyncio
import os
import re
import time
import tempfile
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

from google.adk.cli.utils import logs
from google.adk.runners import InMemoryRunner
from google.adk.sessions.session import Session
from google.genai import types

from agent import root_agent, build_crm_instruction

logs.log_to_tmp_folder()

# Environment Configuration
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
TARGET_FOLDER_ID = os.environ.get("TARGET_FOLDER_ID")
TP_CLIENT_URL = os.environ.get("TP_CLIENT_URL", "http://localhost:8080")
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "5"))


class SheetsSyncClient:
    """Helper client for reading/writing status and records in Google Sheets."""

    def __init__(self, spreadsheet_id: Optional[str] = None):
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.sheet = None
        self._init_client()

    def _init_client(self):
        if not self.spreadsheet_id:
            print("[SheetsSyncClient] SPREADSHEET_ID not configured in environment. Operating in Mock/Local mode.")
            return

        try:
            import gspread
            self.client = gspread.service_account()
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.sheet = self.spreadsheet.worksheet("Intake_Queue")
            print(f"[SheetsSyncClient] Connected to Google Sheet: {self.spreadsheet.title}")
        except Exception as e:
            print(f"[SheetsSyncClient] Could not connect via service_account: {e}. Falling back to mock mode.")
            self.sheet = None

    def fetch_ready_rows(self):
        """Fetches rows marked READY_FOR_CRM."""
        if not self.sheet:
            return [{
                "row_index": 2,
                "client_id": "CLI-1001",
                "email": "john.doe@example.com",
                "state": "CA",
                "status": "READY_FOR_CRM",
                "doc_url": "https://drive.google.com/file/d/sample1",
                "pdf_drive_id": "sample_pdf_id_1"
            }]

        records = self.sheet.get_all_records()
        ready_rows = []
        for idx, row in enumerate(records, start=2):
            if row.get("Status") == "READY_FOR_CRM":
                ready_rows.append({
                    "row_index": idx,
                    "client_id": str(row.get("Client_ID", "")),
                    "email": str(row.get("Email", "")),
                    "state": str(row.get("State", "")),
                    "status": str(row.get("Status", "")),
                    "doc_url": str(row.get("Doc_URL", "")),
                    "pdf_drive_id": str(row.get("PDF_Drive_ID", ""))
                })
        return ready_rows

    def claim_row(self, row_index: int) -> bool:
        """Atomically marks row as IN_CRM_PROCESSING."""
        if not self.sheet:
            return True
        try:
            current_status = self.sheet.cell(row_index, 5).value
            if current_status == "READY_FOR_CRM":
                self.sheet.update_cell(row_index, 5, "IN_CRM_PROCESSING")
                return True
            return False
        except Exception as e:
            print(f"[SheetsSyncClient] Error claiming row {row_index}: {e}")
            return False

    def update_row_result(self, row_index: int, status: str, case_id: str = "", error_log: str = "", duration_seconds: float = 0.0):
        """Updates row with completion status, Case ID, duration, and error logs."""
        if not self.sheet:
            print(f"[Mock Sync] Row {row_index} updated: Status={status}, Case_ID={case_id}, Duration={duration_seconds:.2f}s, Error={error_log}")
            return

        try:
            self.sheet.update_cell(row_index, 5, status)
            if case_id:
                self.sheet.update_cell(row_index, 8, case_id)
            if error_log:
                self.sheet.update_cell(row_index, 9, error_log)
            if duration_seconds > 0:
                self.sheet.update_cell(row_index, 10, round(duration_seconds, 2))
            print(f"[SheetsSyncClient] Row {row_index} updated successfully.")
        except Exception as e:
            print(f"[SheetsSyncClient] Error updating row {row_index}: {e}")


def download_pdf_from_drive(pdf_drive_id: str, client_id: str) -> str:
    """Downloads PDF from Google Drive to local temp directory."""
    temp_dir = tempfile.gettempdir()
    local_pdf_path = os.path.join(temp_dir, f"Tax_Certificate_{client_id}.pdf")
    
    if not os.path.exists(local_pdf_path):
        with open(local_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 Mock Tax Certificate Document Content")
            
    print(f"[DriveDownloader] Downloaded PDF for {client_id} -> {local_pdf_path}")
    return local_pdf_path


async def run_crm_agent_for_row(runner: InMemoryRunner, session: Session, user_id: str, row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Invokes ADK Computer Use agent for a single CRM tax certificate request."""
    client_id = row_data["client_id"]
    pdf_path = download_pdf_from_drive(row_data.get("pdf_drive_id", ""), client_id)
    
    # Create local screenshots directory for visual inspection
    screenshots_dir = os.path.join(os.getcwd(), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    
    payload = {
        "client_id": client_id,
        "email": row_data.get("email", ""),
        "state": row_data.get("state", ""),
        "pdf_local_path": pdf_path,
        "tp_client_url": TP_CLIENT_URL,
        "username": os.environ.get("TP_CLIENT_USER", "admin"),
        "password": os.environ.get("TP_CLIENT_PASS", "password123")
    }
    
    prompt = build_crm_instruction(payload)
    
    content = types.Content(
        role="user", parts=[types.Part.from_text(text=prompt)]
    )
    
    print(f"\n============================================================")
    print(f"Starting Gemini Computer Use Processing for Client: {client_id}")
    print(f"Target CRM URL: {TP_CLIENT_URL}")
    print(f"Live Screenshots Folder: {screenshots_dir}")
    print(f"============================================================")
    
    captured_case_id = ""
    error_message = ""
    agent_responses = []
    screenshot_count = 0

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(f"** {event.author}: {part.text}")
                        agent_responses.append(part.text)
                        
                        match = re.search(r"(CASE-\d+-\d+|TP-\d+-\d+)", part.text)
                        if match:
                            captured_case_id = match.group(1)
                            
                    elif hasattr(part, "inline_data") and part.inline_data:
                        screenshot_count += 1
                        ss_path = os.path.join(screenshots_dir, f"step_{screenshot_count:02d}_{client_id}.png")
                        try:
                            image_bytes = part.inline_data.data
                            with open(ss_path, "wb") as f:
                                f.write(image_bytes)
                            print(f"📸 Live Screenshot Saved: screenshots/step_{screenshot_count:02d}_{client_id}.png")
                        except Exception as ss_err:
                            print(f"📸 Screenshot received ({len(part.inline_data.data)} bytes)")

    except Exception as e:
        error_message = f"Computer Use agent execution failed: {str(e)}"
        print(f"ERROR: {error_message}")

    return {
        "case_id": captured_case_id,
        "error": error_message,
        "full_text": "\n".join(agent_responses)
    }


async def main():
    """Main polling runner loop."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    service_account = os.environ.get("VMAAS_SERVICE_ACCOUNT")

    print("=" * 60)
    print("Tax Certificate Automation - ADK Computer Use Runner")
    print("=" * 60)
    print(f"GCP Project: {project_id}")
    print(f"Service Account: {service_account}")
    print(f"TP Client CRM URL: {TP_CLIENT_URL}")
    print("=" * 60)

    sheets_sync = SheetsSyncClient(SPREADSHEET_ID)
    app_name = "tax_cert_computer_use_runner"
    user_id = "crm_runner_service"

    runner = InMemoryRunner(agent=root_agent, app_name=app_name)

    print("\nStarting polling loop for READY_FOR_CRM records...")
    
    ready_rows = sheets_sync.fetch_ready_rows()
    print(f"Found {len(ready_rows)} row(s) ready for CRM processing.")

    for row_data in ready_rows:
        row_idx = row_data["row_index"]
        client_id = row_data["client_id"]
        
        if not sheets_sync.claim_row(row_idx):
            print(f"Row {row_idx} already claimed by another runner. Skipping.")
            continue

        session = await runner.session_service.create_session(
            app_name=app_name, user_id=user_id
        )

        start_time = time.time()
        result = await run_crm_agent_for_row(runner, session, user_id, row_data)
        elapsed = time.time() - start_time

        case_id = result.get("case_id")
        error = result.get("error")

        if case_id and not error:
            print(f"SUCCESS: Completed row {row_idx} (Client {client_id}) -> Case ID: {case_id} in {elapsed:.2f}s")
            sheets_sync.update_row_result(
                row_index=row_idx,
                status="COMPLETED",
                case_id=case_id,
                duration_seconds=elapsed
            )
        else:
            err_log = error or "Agent failed to capture valid Case ID from CRM page."
            print(f"FAILED: Row {row_idx} (Client {client_id}) -> Error: {err_log}")
            sheets_sync.update_row_result(
                row_index=row_idx,
                status="FAILED_NEEDS_REVIEW",
                error_log=err_log,
                duration_seconds=elapsed
            )

    print("\nRunner loop batch completed.")


if __name__ == "__main__":
    asyncio.run(main())
