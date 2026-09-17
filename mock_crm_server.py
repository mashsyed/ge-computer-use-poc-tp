"""Multi-Threaded Fast Mock CRM Web Application with Email Outbox Inspector.

Provides robust multi-threaded request handling for Playwright and browser automation.
"""

import http.server
import socketserver
import os
import random
import smtplib
import sys
import urllib.parse
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SENT_EMAILS = []

MOCK_CLIENTS = {
    "CLI-1001": {
        "client_id": "CLI-1001",
        "name": "John Doe Enterprise",
        "email": "mashsyed@google.com",
        "state": "Amazonas",
        "credit_card_balance": "$2,450.00",
        "loan_balance": "$35,000.00",
        "standing": "GOOD_STANDING"
    },
    "CLI-1005": {
        "client_id": "CLI-1005",
        "name": "Bogotá Corp",
        "email": "mashsyed@google.com",
        "state": "Bogotá",
        "credit_card_balance": "$1,200.00",
        "loan_balance": "$45,000.00",
        "standing": "GOOD_STANDING"
    }
}

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TP Client CRM - Login</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; margin: 0; padding: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }
        .login-card { background: white; width: 400px; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-top: 4px solid #1a73e8; }
        .login-card h2 { margin-top: 0; color: #202124; font-size: 24px; text-align: center; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 6px; font-weight: 600; color: #5f6368; }
        .form-group input { width: 100%; padding: 12px; border: 1px solid #dadce0; border-radius: 4px; box-sizing: border-box; font-size: 14px; }
        .btn-submit { width: 100%; padding: 12px; background-color: #1a73e8; color: white; border: none; border-radius: 4px; font-size: 16px; font-weight: 600; cursor: pointer; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>TP Client CRM Login</h2>
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Username / Agent ID</label>
                <input type="text" id="username" name="username" placeholder="Enter username (e.g. admin)" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Enter password" required>
            </div>
            <button type="submit" id="btn-login" class="btn-submit">Sign In to TP Client</button>
        </form>
    </div>
</body>
</html>"""

CUSTOMER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TP Client CRM - Customer & Case Portal</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; margin: 0; padding: 0; }
        .navbar { background-color: #1a73e8; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .navbar h1 { margin: 0; font-size: 20px; font-weight: 600; }
        .container { max-width: 1000px; margin: 30px auto; padding: 0 20px; }
        .search-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; gap: 10px; }
        .search-box input { flex: 1; padding: 12px; border: 1px solid #dadce0; border-radius: 4px; font-size: 15px; }
        .search-box button { padding: 12px 24px; background-color: #1a73e8; color: white; border: none; border-radius: 4px; font-weight: 600; cursor: pointer; }
        .card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); margin-bottom: 25px; }
        .card h2 { margin-top: 0; color: #202124; font-size: 18px; border-bottom: 2px solid #f1f3f4; padding-bottom: 10px; }
        .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; }
        .detail-item { font-size: 14px; }
        .detail-item label { color: #5f6368; font-weight: 600; display: block; }
        .detail-item span { color: #202124; font-weight: 500; font-size: 16px; }
        .form-row { margin-bottom: 15px; }
        .form-row label { display: block; margin-bottom: 5px; font-weight: 600; color: #5f6368; }
        .form-row input, .form-row select, .form-row textarea { width: 100%; padding: 10px; border: 1px solid #dadce0; border-radius: 4px; box-sizing: border-box; font-size: 14px; }
        .btn-create { background-color: #34a853; color: white; padding: 12px 24px; border: none; border-radius: 4px; font-weight: 600; cursor: pointer; font-size: 15px; }
        .success-banner { background-color: #e6f4ea; border: 1px solid #ceedd5; color: #137333; padding: 15px; border-radius: 6px; margin-bottom: 20px; font-size: 16px; font-weight: 600; }
        .case-id-highlight { background-color: #fef7e0; border: 1px dashed #f9ab00; padding: 10px; border-radius: 4px; display: inline-block; font-family: monospace; font-size: 18px; color: #b06000; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>TP Client CRM - Agent Portal</h1>
        <div><a href="/outbox" style="color: white; font-weight: bold;">📧 View Sent Email Outbox</a></div>
    </div>

    <div class="container">
        <!--CASE_BANNER_HTML-->
        <div class="search-box">
            <form method="GET" action="/customer" style="display: flex; width: 100%; gap: 10px;">
                <input type="text" id="search-client-id" name="client_id" value="<!--CLIENT_ID_VAL-->" placeholder="Enter Client ID (e.g., CLI-1005)..." required>
                <button type="submit" id="btn-search">Search Client</button>
            </form>
        </div>
        <!--CLIENT_DETAILS_HTML-->
    </div>
</body>
</html>"""


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class MockCRMHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ["/", "/login"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(LOGIN_HTML.encode("utf-8"))
        elif path == "/customer":
            client_id = query.get("client_id", [""])[0].strip().upper()
            case_id = query.get("created_case_id", [""])[0]
            self.render_customer(client_id, case_id)
        elif path == "/outbox":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Dispatched Emails</h1>")
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get("Content-Length", 0))
        body_data = self.rfile.read(content_length)

        if path == "/login":
            self.send_response(302)
            self.send_header("Location", "/customer")
            self.end_headers()

        elif path == "/customer/create-case":
            case_num = random.randint(10000, 99999)
            generated_case_id = f"CASE-2026-{case_num}"
            
            body_str = body_data.decode("utf-8", errors="ignore")
            form_params = urllib.parse.parse_qs(body_str)
            client_id = form_params.get("client_id", ["CLI-1005"])[0]

            redirect_url = f"/customer?client_id={urllib.parse.quote(client_id)}&created_case_id={generated_case_id}"
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.end_headers()
        else:
            self.send_error(404)

    def render_customer(self, client_id, created_case_id=""):
        case_banner_html = ""
        if created_case_id:
            case_banner_html = f"""
            <div class="success-banner">
                <div>✓ Tax Certificate Case Created & Dispatched Successfully!</div>
                <div>Generated Case ID: <div class="case-id-highlight" id="generated-case-id">{created_case_id}</div></div>
            </div>"""

        client = MOCK_CLIENTS.get(client_id, {
            "client_id": client_id or "CLI-1005",
            "name": f"Client {client_id} Corp",
            "email": "mashsyed@google.com",
            "state": "Bogotá",
            "loan_balance": "$45,000.00",
            "standing": "GOOD_STANDING"
        })

        client_details_html = f"""
        <div class="card">
            <h2>Client Profile Record</h2>
            <div class="detail-grid">
                <div class="detail-item"><label>Client ID</label><span id="display-client-id">{client['client_id']}</span></div>
                <div class="detail-item"><label>Client Name</label><span>{client['name']}</span></div>
                <div class="detail-item"><label>Email Address</label><span id="display-client-email">{client['email']}</span></div>
                <div class="detail-item"><label>State Jurisdiction</label><span id="display-client-state">{client['state']}</span></div>
            </div>
        </div>

        <div class="card">
            <h2>Create New Tax Certificate Case</h2>
            <form method="POST" action="/customer/create-case">
                <input type="hidden" name="client_id" value="{client['client_id']}">
                <button type="submit" id="btn-submit-case" class="btn-create">Submit Case & Dispatch Email</button>
            </form>
        </div>"""

        content = (
            CUSTOMER_HTML
            .replace("<!--CASE_BANNER_HTML-->", case_banner_html)
            .replace("<!--CLIENT_ID_VAL-->", client_id)
            .replace("<!--CLIENT_DETAILS_HTML-->", client_details_html)
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = ThreadedHTTPServer(("0.0.0.0", port), MockCRMHandler)
    print(f"Server running on port {port}")
    server.serve_forever()
