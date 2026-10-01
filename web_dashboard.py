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

"""Modern Web UI Dashboard for Gemini Computer Use Generalized Platform.

Launches a local web server at http://localhost:8501 with an interactive interface
for entering URLs, task prompts, watching execution logs, and viewing cost metrics.
"""

import asyncio
import json
import os
import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

from adaptive_agent import run_adaptive_automation
from script_cache import CACHE_DIR

PORT = 8501

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini Computer Use Generalized Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; }
        .form-control, .form-select { background-color: #0f172a; border: 1px solid #475569; color: #f8fafc; }
        .form-control:focus { background-color: #0f172a; color: #fff; border-color: #3b82f6; box-shadow: none; }
        .btn-primary { background: linear-gradient(135deg, #2563eb, #1d4ed8); border: none; font-weight: 600; padding: 10px 24px; }
        .btn-primary:hover { background: linear-gradient(135deg, #1d4ed8, #1e40af); }
        .badge-decision { font-size: 0.95rem; padding: 8px 14px; border-radius: 20px; }
        .console-output { background-color: #020617; border: 1px solid #1e293b; font-family: monospace; font-size: 0.88rem; color: #38bdf8; height: 320px; overflow-y: auto; padding: 12px; border-radius: 8px; }
        .table-dark { --bs-table-bg: #1e293b; --bs-table-border-color: #334155; }
        .metric-val { font-size: 1.5rem; font-weight: 700; color: #38bdf8; }
    </style>
</head>
<body class="py-4">
    <div class="container max-width-lg">
        <!-- Header -->
        <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
            <div>
                <h2 class="fw-bold mb-1">🚀 Gemini Computer Use Generalized Platform</h2>
                <p class="text-secondary mb-0">Adaptive Browser Automation with Gemini 3.8 Flash & Playwright</p>
            </div>
            <div>
                <span class="badge bg-primary fs-6 px-3 py-2">Gemini 3.8 Flash</span>
            </div>
        </div>

        <div class="row g-4">
            <!-- Left Panel: Form Input -->
            <div class="col-lg-6">
                <div class="card p-4 shadow-sm mb-4">
                    <h5 class="fw-bold text-white mb-3">🌐 Execute Automation Request</h5>
                    <form id="runForm">
                        <div class="mb-3">
                            <label class="form-label fw-semibold text-slate-300">Target Website URL</label>
                            <input type="url" id="targetUrl" class="form-control" placeholder="http://localhost:8080/login" value="http://localhost:8080/login" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-semibold text-slate-300">Task Instructions & Prompt</label>
                            <textarea id="userPrompt" class="form-control" rows="4" placeholder="Describe the steps (e.g. Log in with admin/password123, search CLI-1007, and submit case)..." required>Log into CRM as admin / password123, search client CLI-1007, and submit case.</textarea>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-semibold text-slate-300">Google OAuth Access Token <span class="text-secondary font-monospace small">(Optional - overrides expired token)</span></label>
                            <input type="password" id="oauthToken" class="form-control font-monospace small" placeholder="ya29.a0AdMD...">
                        </div>
                        <div class="form-check mb-4">
                            <input class="form-check-input" type="checkbox" id="headlessMode">
                            <label class="form-check-label text-slate-300" for="headlessMode">
                                Run in Headless Mode (Hide Chrome Browser Window)
                            </label>
                        </div>
                        <button type="submit" id="submitBtn" class="btn btn-primary w-100 py-2">
                            ▶️ Run Adaptive Automation
                        </button>
                    </form>
                </div>

                <!-- Decision State Banner -->
                <div id="decisionCard" class="card p-4 shadow-sm text-center d-none">
                    <h6 class="text-secondary text-uppercase mb-2 fw-semibold">Smart Decision Engine State</h6>
                    <div id="decisionBadge" class="badge badge-decision bg-info text-dark">Evaluating URL...</div>
                </div>
            </div>

            <!-- Right Panel: Execution Metrics & Output -->
            <div class="col-lg-6">
                <!-- Summary Metrics Cards -->
                <div class="row g-3 mb-4">
                    <div class="col-6">
                        <div class="card p-3 text-center">
                            <span class="text-secondary small fw-semibold">TOTAL RUN COST</span>
                            <div class="metric-val" id="metricCost">$0.000000</div>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="col card p-3 text-center">
                            <span class="text-secondary small fw-semibold">1,000 RUN ESTIMATE</span>
                            <div class="metric-val text-success" id="metric1k">$0.00</div>
                        </div>
                    </div>
                </div>

                <!-- Live Execution Console -->
                <div class="card p-4 shadow-sm mb-4">
                    <h5 class="fw-bold text-white mb-3">🖥️ Live Execution Logs</h5>
                    <pre class="console-output mb-0" id="consoleLogs">Waiting for automation execution request...</pre>
                </div>
            </div>
        </div>

        <!-- Cost Table Breakdown -->
        <div class="row mt-2">
            <div class="col-12">
                <div class="card p-4 shadow-sm">
                    <h5 class="fw-bold text-white mb-3">💰 Itemized Step & Cost Breakdown</h5>
                    <div class="table-responsive">
                        <table class="table table-dark table-hover align-middle mb-0">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Step / Action</th>
                                    <th>Execution Type</th>
                                    <th>Input Tokens</th>
                                    <th>Output Tokens</th>
                                    <th>Cost (USD)</th>
                                </tr>
                            </thead>
                            <tbody id="costTableBody">
                                <tr>
                                    <td colspan="6" class="text-center text-secondary py-3">No run data recorded yet. Execute a prompt above.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('runForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            const url = document.getElementById('targetUrl').value;
            const prompt = document.getElementById('userPrompt').value;
            const oauthToken = document.getElementById('oauthToken').value;
            const headless = document.getElementById('headlessMode').checked;
            const consoleBox = document.getElementById('consoleLogs');
            const decisionCard = document.getElementById('decisionCard');
            const decisionBadge = document.getElementById('decisionBadge');

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Executing Adaptive Engine...';
            consoleBox.innerText = `[Initiating Request]\nTarget URL: ${url}\nPrompt: ${prompt}\n\nRunning Adaptive Decision Engine...\n`;

            decisionCard.classList.remove('d-none');
            decisionBadge.className = 'badge badge-decision bg-warning text-dark';
            decisionBadge.innerText = '🔍 Checking Site Cache & UI Fingerprint...';

            try {
                const response = await fetch('/api/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url, prompt: prompt, token: oauthToken, headless: headless })
                });

                const data = await response.json();
                consoleBox.innerText = data.logs || 'Execution finished.';

                if (data.decision_state) {
                    if (data.decision_state === 'FAST_PATH') {
                        decisionBadge.className = 'badge badge-decision bg-success text-white';
                        decisionBadge.innerText = '🚀 Fast-Path Activated (Zero-Token Playwright)';
                    } else if (data.decision_state === 'BRAND_NEW_URL') {
                        decisionBadge.className = 'badge badge-decision bg-info text-dark';
                        decisionBadge.innerText = '🆕 Brand New URL (Initial Gemini Mapping)';
                    } else if (data.decision_state === 'UI_SHIFT_SELF_HEALING') {
                        decisionBadge.className = 'badge badge-decision bg-warning text-dark';
                        decisionBadge.innerText = '🧠 UI Shift Detected (Gemini Self-Healing)';
                    } else if (data.decision_state === 'AUTH_REQUIRED') {
                        decisionBadge.className = 'badge badge-decision bg-danger text-white';
                        decisionBadge.innerText = '🔐 Authentication Required (gcloud ADC expired)';
                    } else {
                        decisionBadge.className = 'badge badge-decision bg-secondary text-white';
                        decisionBadge.innerText = data.decision_state;
                    }
                }

                document.getElementById('metricCost').innerText = `$${(data.total_cost || 0).toFixed(6)}`;
                document.getElementById('metric1k').innerText = `$${((data.total_cost || 0) * 1000).toFixed(2)}`;

            } catch (err) {
                consoleBox.innerText += `\n❗️ Error: ${err}`;
                decisionBadge.className = 'badge badge-decision bg-danger text-white';
                decisionBadge.innerText = '❌ Execution Error';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '▶️ Run Adaptive Automation';
            }
        });
    </script>
</body>
</html>
"""


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler serving the Web Dashboard SPA and JSON API endpoints."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/run":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            target_url = data.get("url", "http://localhost:8080/login")
            prompt = data.get("prompt", "Log in as admin / password123, search CLI-1007, and submit case.")
            token = data.get("token", "")
            headless = data.get("headless", False)

            if token:
                os.environ["GOOGLE_OAUTH_TOKEN"] = token

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    run_adaptive_automation(target_url, prompt, headless=headless)
                )
                
                resp_payload = {
                    "status": result.get("status", "SUCCESS"),
                    "total_cost": result.get("total_cost_usd", 0.0),
                    "decision_state": result.get("decision_state", "BRAND_NEW_URL"),
                    "error": result.get("error", ""),
                    "logs": f"Status: {result.get('status')}\nDecision State: {result.get('decision_state')}\n" + (f"Error: {result.get('error')}\n" if result.get('error') else "") + f"Total Cost: ${result.get('total_cost_usd', 0.0):.6f} USD"
                }
            except Exception as e:
                resp_payload = {
                    "status": "ERROR",
                    "error": str(e),
                    "logs": f"Error executing automation: {e}"
                }
            finally:
                loop.close()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp_payload).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def start_dashboard():
    server = HTTPServer(("0.0.0.0", PORT), DashboardRequestHandler)
    print("=" * 65)
    print(f"🚀 WEB DASHBOARD RUNNING AT: http://localhost:{PORT}")
    print("=" * 65)
    server.serve_forever()


if __name__ == "__main__":
    start_dashboard()
