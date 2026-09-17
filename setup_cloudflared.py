"""Standalone Cloudflare Tunnel Launcher for macOS.

Uses the local 'cloudflared' binary to expose http://localhost:8080 
over a free, enterprise-grade Cloudflare HTTPS URL (https://*.trycloudflare.com).
No Node, No npm, No npx, and No landing pages!
"""

import os
import re
import subprocess
import sys

CLOUDFLARED_PATH = os.path.join(os.getcwd(), "cloudflared")

def start_tunnel(port=8080):
    if not os.path.exists(CLOUDFLARED_PATH):
        print(f"Error: {CLOUDFLARED_PATH} not found.")
        return

    print("\n" + "=" * 65)
    print(f"Launching Cloudflare Tunnel for http://localhost:{port}...")
    print("=" * 65 + "\n")

    cmd = [CLOUDFLARED_PATH, "tunnel", "--url", f"http://localhost:{port}"]
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    tunnel_url = None
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match and not tunnel_url:
                tunnel_url = match.group(0)
                print("\n" + "*" * 65)
                print("  🚀 SUCCESS! YOUR CLOUDFLARE TUNNEL URL IS:")
                print(f"  {tunnel_url}")
                print("*" * 65)
                print(f"\n1. Update your .env file with:")
                print(f"   TP_CLIENT_URL={tunnel_url}")
                print(f"\n2. Leave this script running and run `python3 main.py` in your other terminal.\n")
                
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping Cloudflare tunnel...")
        proc.terminate()

if __name__ == "__main__":
    start_tunnel(8080)
