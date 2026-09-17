"""Instant Email Tester for Gmail / Google Workspace SMTP.

Tests your GMAIL_SENDER and GMAIL_APP_PASSWORD configured in .env.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def load_env():
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("'\"")

load_env()

sender = os.environ.get("GMAIL_SENDER")
app_password = os.environ.get("GMAIL_APP_PASSWORD")
recipient = os.environ.get("TEST_RECIPIENT_EMAIL", sender)

print("=" * 60)
print("📧 Testing SMTP Email Delivery")
print("=" * 60)
print(f"Sender: {sender}")
print(f"Recipient: {recipient}")
print(f"App Password Length: {len(app_password) if app_password else 0} chars")
print("=" * 60)

if not sender or not app_password:
    print("❌ Missing GMAIL_SENDER or GMAIL_APP_PASSWORD in .env")
    exit(1)

try:
    msg = MIMEMultipart()
    msg["From"] = f"TP Client CRM <{sender}>"
    msg["To"] = recipient
    msg["Subject"] = "✅ Test Email - Tax Certificate CRM Automation"

    body = """Hello!

This is a test email sent via Python SMTP using your Google App Password.
Your email dispatch configuration for the Tax Certificate CRM automation is working 100%!
"""
    msg.attach(MIMEText(body, "plain"))

    print("Connecting to smtp.gmail.com:587...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, app_password)
        print("✓ Authentication successful!")
        server.send_message(msg)

    print("\n🎉 SUCCESS! Test email delivered successfully to:", recipient)
    print("Check your inbox!")

except Exception as e:
    print("\n❌ SMTP Delivery Failed:", e)
    print("\nTip: Generate a 16-character App Password at https://myaccount.google.com/apppasswords")
