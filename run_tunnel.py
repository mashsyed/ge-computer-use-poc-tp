"""Simple ngrok tunnel launcher using pyngrok.

Exposes http://localhost:8080 over a public ngrok HTTPS URL for Vertex AI Sandbox Computer.
"""

import sys
from pyngrok import ngrok

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Launching ngrok tunnel for local port {port}...")
    
    try:
        # Start tunnel on local port
        tunnel = ngrok.connect(port)
        public_url = tunnel.public_url
        
        print("\n" + "=" * 65)
        print(f"  🚀 SUCCESS! YOUR PUBLIC TUNNEL URL IS:")
        print(f"  {public_url}")
        print("=" * 65)
        print(f"\n1. Copy this line into your .env file:")
        print(f"   TP_CLIENT_URL={public_url}")
        print(f"\n2. Leave this script running and run `python3 main.py` in your other terminal.\n")
        
        ngrok_process = ngrok.get_ngrok_process()
        ngrok_process.proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down ngrok tunnel...")
        ngrok.kill()
    except Exception as e:
        print(f"\nError starting ngrok tunnel: {e}")

if __name__ == "__main__":
    main()
