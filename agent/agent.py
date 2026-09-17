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

"""ADK Agent initialization with Gemini Computer Use tool in Vertex AI Sandbox."""

import os

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

from google.adk import Agent
from google.adk.integrations.vmaas import AgentEngineSandboxComputer
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset

# Configuration from environment variables
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
SERVICE_ACCOUNT = os.environ.get("VMAAS_SERVICE_ACCOUNT")

SANDBOX_NAME = os.environ.get("SANDBOX_NAME") or os.environ.get("VMAAS_SANDBOX_NAME")
SANDBOX_TEMPLATE_NAME = os.environ.get("VMAAS_SANDBOX_TEMPLATE_NAME")
SANDBOX_SNAPSHOT_NAME = os.environ.get("VMAAS_SANDBOX_SNAPSHOT_NAME")

MODEL_NAME = os.environ.get("COMPUTER_USE_MODEL", "gemini-2.5-computer-use-preview-10-2025")

# Initialize Sandbox Computer
sandbox_computer = AgentEngineSandboxComputer(
    project_id=PROJECT_ID,
    service_account_email=SERVICE_ACCOUNT,
    sandbox_name=SANDBOX_NAME,
    sandbox_template_name=SANDBOX_TEMPLATE_NAME,
    sandbox_snapshot_name=SANDBOX_SNAPSHOT_NAME,
    search_engine_url="https://www.google.com",
)

# Root Agent definition with Computer Use Toolset
root_agent = Agent(
    model=MODEL_NAME,
    name="tax_certificate_crm_agent",
    description=(
        "An ADK computer use agent that navigates the TP Client CRM web application"
        " in a secure sandbox to process tax certificate requests."
    ),
    instruction="""You are an expert browser automation agent using Computer Use to operate
the TP Client CRM web portal.

Your core operational guidelines:
1. Carefully follow step-by-step navigation instructions for CRM authentication, client search, case creation, and document attachment.
2. Observe browser screenshot state after each action step before taking the next action.
3. Locate elements visually using semantic labels, input placeholders, and button text.
4. Extract and report the generated Case ID upon successful case creation.
5. If an unrecoverable navigation error occurs, capture the screen state and report the issue clearly.
""",
    tools=[ComputerUseToolset(computer=sandbox_computer)],
)
