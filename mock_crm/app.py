"""Mock TP Client CRM Web Application with Sent Email Inspector (/outbox).

Provides a complete CRM web application:
1. Login Page (/ or /login): Authentication form for CRM agents.
2. Customer Page (/customer): Client lookup, details view, case creation form, file attachment, and Case_ID generation.
3. Sent Email Outbox (/outbox): Captures and renders all dispatched emails with full HTML body, recipient info, 
   timestamp, and downloadable Tax Certificate PDF attachments.
4. Optional Gmail SMTP integration if personal @gmail.com App Password is provided.
"""

import http.server
import os
import random
import smtplib
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

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

SENT_EMAILS = []

MOCK_CLIENTS = {
    "CLI-1001": {
        "client_id": "CLI-1001",
        "name": "John Doe Enterprise",
        "email": os.environ.get("TEST_RECIPIENT_EMAIL", "admin@mashsyed.altostrat.com"),
        "state": "CA",
        "credit_card_balance": "$2,450.00",
        "loan_balance": "$35,000.00",
        "standing": "GOOD_STANDING"
    },
    "CLI-1002": {
        "client_id": "CLI-1002",
        "name": "Jane Smith LLC",
        "email": "jane.smith@example.com",
        "state": "NY",
        "credit_card_balance": "$0.00",
        "loan_balance": "$12,500.00",
        "standing": "GOOD_STANDING"
    },
    "CLI-1003": {
        "client_id": "CLI-1003",
        "name": "Robert Johnson Inc",
        "email": "robert.johnson@example.com",
        "state": "TX",
        "credit_card_balance": "$8,900.50",
        "loan_balance": "$78,000.00",
        "standing": "UNDER_REVIEW"
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
        .form-group input:focus { border-color: #1a73e8; outline: none; }
        .btn-submit { width: 100%; padding: 12px; background-color: #1a73e8; color: white; border: none; border-radius: 4px; font-size: 16px; font-weight: 600; cursor: pointer; }
        .btn-submit:hover { background-color: #1557b0; }
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
        .user-info { font-size: 14px; }
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
        .btn-create:hover { background-color: #2d8e47; }
        .success-banner { background-color: #e6f4ea; border: 1px solid #ceedd5; color: #137333; padding: 15px; border-radius: 6px; margin-bottom: 20px; font-size: 16px; font-weight: 600; }
        .case-id-highlight { background-color: #fef7e0; border: 1px dashed #f9ab00; padding: 10px; border-radius: 4px; display: inline-block; font-family: monospace; font-size: 18px; color: #b06000; margin-top: 5px; }
        .btn-outbox { background-color: #ffffff; color: #1a73e8; border: 1px solid #1a73e8; padding: 6px 14px; border-radius: 4px; font-weight: 600; text-decoration: none; margin-left: 15px; }
        .btn-outbox:hover { background-color: #e8f0fe; }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>TP Client CRM - Agent Portal</h1>
        <div class="user-info">
            Logged in as: <strong><!--USERNAME--></strong> 
            <a href="/outbox" class="btn-outbox">📧 View Sent Outbox (<!--OUTBOX_COUNT-->)</a>
            | <a href="/logout" style="color: white; text-decoration: underline; margin-left: 10px;">Logout</a>
        </div>
    </div>

    <div class="container">
        <!--CASE_BANNER_HTML-->

        <!-- Search Bar -->
        <div class="search-box">
            <form method="GET" action="/customer" style="display: flex; width: 100%; gap: 10px;">
                <input type="text" id="search-client-id" name="client_id" value="<!--CLIENT_ID_VAL-->" placeholder="Enter Client ID (e.g., CLI-1001)..." required>
                <button type="submit" id="btn-search">Search Client</button>
            </form>
        </div>

        <!--CLIENT_DETAILS_HTML-->
    </div>
</body>
</html>"""

OUTBOX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TP Client CRM - Sent Email Outbox</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; margin: 0; padding: 0; }
        .navbar { background-color: #1a73e8; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .navbar h1 { margin: 0; font-size: 20px; font-weight: 600; }
        .container { max-width: 900px; margin: 30px auto; padding: 0 20px; }
        .email-card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 20px; border-left: 5px solid #34a853; }
        .email-header { border-bottom: 1px solid #e8eaed; padding-bottom: 12px; margin-bottom: 15px; }
        .email-header div { margin-bottom: 4px; font-size: 14px; }
        .email-header strong { color: #202124; }
        .email-body { background: #f8f9fa; padding: 15px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; font-size: 14px; color: #3c4043; border: 1px solid #dadce0; }
        .badge { background: #e6f4ea; color: #137333; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; display: inline-block; margin-bottom: 10px; }
        .btn-back { background: #1a73e8; color: white; padding: 10px 20px; border-radius: 4px; text-decoration: none; font-weight: 600; display: inline-block; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>TP Client CRM - Dispatched Email Outbox</h1>
        <div><a href="/customer?client_id=CLI-1001" style="color: white; text-decoration: underline;">Back to CRM Portal</a></div>
    </div>

    <div class="container">
        <a href="/customer?client_id=CLI-1001" class="btn-back">← Back to Agent Portal</a>
        <h2>Sent Email Dispatches (<!--TOTAL_COUNT-->)</h2>
        <!--OUTBOX_ITEMS-->
    </div>
</body>
</html>"""


def dispatch_email(recipient_email: str, case_id: str, client_id: str, comments: str):
    """Dispatches email to Sent Email Outbox inspector and attempts Gmail SMTP if configured."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    email_record = {
        "timestamp": timestamp,
        "case_id": case_id,
        "client_id": client_id,
        "recipient": recipient_email,
        "subject": f"Official Tax Certificate Dispatched - Case {case_id} ({client_id})",
        "body": f"""Dear Client ({client_id}),

Your Tax Certificate Case has been successfully created and processed on the TP Client CRM portal.

Case Details:
- Case ID: {case_id}
- Client ID: {client_id}
- Tax Year: 2025
- Dispatch Notes: {comments}

Attachment: Tax_Certificate_{client_id}.pdf (Official Signed Tax Document)

Best regards,
TP Client CRM Automation Team""",
        "attachment": f"Tax_Certificate_{client_id}.pdf"
    }
    
    SENT_EMAILS.insert(0, email_record)
    print(f"📧 [EMAIL DISPATCHED TO OUTBOX] Case {case_id} -> Recipient: {recipient_email}")

    # Optional Gmail SMTP attempt if user provided personal @gmail.com App Password
    gmail_sender = os.environ.get("GMAIL_SENDER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if gmail_sender and gmail_password and "gmail.com" in gmail_sender.lower():
        try:
            msg = MIMEMultipart()
            msg["From"] = f"TP Client CRM <{gmail_sender}>"
            msg["To"] = recipient_email
            msg["Subject"] = email_record["subject"]
            msg.attach(MIMEText(email_record["body"], "plain"))

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(gmail_sender, gmail_password)
                server.send_message(msg)
                print(f"✓ [GMAIL SMTP DELIVERED] Sent live email to {recipient_email}!")
        except Exception as e:
            print(f"⚠️ [SMTP Note] Live Gmail SMTP fallback skipped: {e}")


class MockCRMHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for Mock TP Client CRM."""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ["/", "/login"]:
            self.render_login()
        elif path == "/customer":
            client_id = query.get("client_id", [""])[0].strip().upper()
            case_id = query.get("created_case_id", [""])[0]
            self.render_customer(client_id, case_id)
        elif path == "/outbox":
            self.render_outbox()
        elif path == "/logout":
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
        else:
            self.send_error(404, "Page Not Found")

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
            
            client_id = form_params.get("client_id", ["CLI-1001"])[0]
            email = form_params.get("email", [os.environ.get("TEST_RECIPIENT_EMAIL", "admin@mashsyed.altostrat.com")])[0]
            comments = form_params.get("comments", ["Tax Certificate verified."])[0]

            dispatch_email(recipient_email=email, case_id=generated_case_id, client_id=client_id, comments=comments)

            redirect_url = f"/customer?client_id={urllib.parse.quote(client_id)}&created_case_id={generated_case_id}"
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.end_headers()

        else:
            self.send_error(404, "Endpoint Not Found")

    def render_login(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(LOGIN_HTML.encode("utf-8"))

    def render_outbox(self):
        items_html = ""
        if not SENT_EMAILS:
            items_html = '<div style="text-align: center; color: #5f6368; padding: 40px; background: white; border-radius: 8px;">No emails dispatched yet. Submit a case in the agent portal to see sent emails here.</div>'
        else:
            for item in SENT_EMAILS:
                items_html += f"""
                <div class="email-card">
                    <div class="badge">✓ SENT VIA CRM EMAIL DISPATCH SYSTEM</div>
                    <div class="email-header">
                        <div><strong>Timestamp:</strong> {item['timestamp']}</div>
                        <div><strong>To:</strong> {item['recipient']}</div>
                        <div><strong>Subject:</strong> {item['subject']}</div>
                        <div><strong>Attachment:</strong> 📎 <span style="font-family: monospace;">{item['attachment']}</span></div>
                    </div>
                    <div class="email-body">{item['body']}</div>
                </div>"""

        content = OUTBOX_HTML.replace("<!--TOTAL_COUNT-->", str(len(SENT_EMAILS))).replace("<!--OUTBOX_ITEMS-->", items_html)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def render_customer(self, client_id, created_case_id=""):
        username = "Agent_User"
        
        case_banner_html = ""
        if created_case_id:
            case_banner_html = f"""
            <div class="success-banner">
                <div>✓ Tax Certificate Case Created & Dispatched Successfully!</div>
                <div style="margin-top: 8px;">
                    Generated Case ID: <div class="case-id-highlight" id="generated-case-id">{created_case_id}</div>
                </div>
                <div style="font-size: 13px; font-weight: normal; margin-top: 8px;">
                    📧 Email dispatched with Tax Certificate PDF. <a href="/outbox" style="color: #137333; font-weight: bold; text-decoration: underline;">Click here to view Sent Email Outbox →</a>
                </div>
            </div>"""

        client = MOCK_CLIENTS.get(client_id) if client_id else None
        
        if client_id and not client:
            client = {
                "client_id": client_id,
                "name": f"Client {client_id} Corp",
                "email": os.environ.get("TEST_RECIPIENT_EMAIL", f"contact@{client_id.lower()}.com"),
                "state": "CA",
                "credit_card_balance": "$1,000.00",
                "loan_balance": "$25,000.00",
                "standing": "GOOD_STANDING"
            }

        client_details_html = ""
        if client:
            client_details_html = f"""
            <div class="card">
                <h2>Client Profile Record</h2>
                <div class="detail-grid">
                    <div class="detail-item"><label>Client ID</label><span id="display-client-id">{client['client_id']}</span></div>
                    <div class="detail-item"><label>Client Name</label><span>{client['name']}</span></div>
                    <div class="detail-item"><label>Email Address</label><span id="display-client-email">{client['email']}</span></div>
                    <div class="detail-item"><label>State Jurisdiction</label><span id="display-client-state">{client['state']}</span></div>
                    <div class="detail-item"><label>Loan Balance</label><span id="display-loan-balance">{client['loan_balance']}</span></div>
                    <div class="detail-item"><label>Account Standing</label><span style="color: #137333; font-weight: bold;">{client['standing']}</span></div>
                </div>
            </div>

            <div class="card">
                <h2>Create New Tax Certificate Case</h2>
                <form method="POST" action="/customer/create-case">
                    <input type="hidden" name="client_id" value="{client['client_id']}">
                    <input type="hidden" name="email" value="{client['email']}">
                    <input type="hidden" name="state" value="{client['state']}">

                    <div class="form-row">
                        <label for="case_category">Case Category / Type</label>
                        <select id="case_category" name="case_category" required>
                            <option value="Tax Certificate Request" selected>Tax Certificate Request</option>
                            <option value="Loan Statement">Loan Statement</option>
                        </select>
                    </div>

                    <div class="form-row">
                        <label for="tax_year">Tax Year</label>
                        <input type="text" id="tax_year" name="tax_year" value="2025" required>
                    </div>

                    <div class="form-row">
                        <label for="loan_balance_summary">Verified Financial Balance Summary</label>
                        <input type="text" id="loan_balance_summary" name="loan_balance_summary" value="{client['loan_balance']}" readonly>
                    </div>

                    <div class="form-row">
                        <label for="pdf_file">Attach Tax Certificate PDF Document</label>
                        <input type="file" id="pdf_file" name="pdf_file" accept=".pdf">
                    </div>

                    <div class="form-row">
                        <label for="comments">Response Message / Dispatch Notes</label>
                        <textarea id="comments" name="comments" rows="3">Please find attached your official Tax Certificate for tax year 2025.</textarea>
                    </div>

                    <button type="submit" id="btn-submit-case" class="btn-create">Submit Case & Dispatch Email</button>
                </form>
            </div>"""
        else:
            client_details_html = """
            <div class="card" style="text-align: center; color: #5f6368; padding: 50px;">
                <p>Please enter a Client ID above (e.g. <strong>CLI-1001</strong>, <strong>CLI-1002</strong>, <strong>CLI-1003</strong>) and click <strong>Search Client</strong> to view profile and submit a tax certificate case.</p>
            </div>"""

        content = (
            CUSTOMER_HTML
            .replace("<!--USERNAME-->", username)
            .replace("<!--CASE_BANNER_HTML-->", case_banner_html)
            .replace("<!--CLIENT_ID_VAL-->", client_id if client else "")
            .replace("<!--CLIENT_DETAILS_HTML-->", client_details_html)
            .replace("<!--OUTBOX_COUNT-->", str(len(SENT_EMAILS)))
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))


def run_server(port=8080):
    server_address = ("0.0.0.0", port)
    httpd = http.server.HTTPServer(server_address, MockCRMHandler)
    print(f"Starting TP Client CRM server on http://localhost:{port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8080))
    run_server(port_arg)
