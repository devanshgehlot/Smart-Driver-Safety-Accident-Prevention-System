import http.server
import socketserver
import socket
import sys
import os

PORT = 8000

def get_local_ip():
    try:
        # Create a dummy socket connection to detect local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean logging output
        sys.stdout.write(f"[Request] {args[0]} - {args[1]}\n")

def run_server():
    # Change working directory to the directory of this script to avoid 404 errors
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    local_ip = get_local_ip()
    handler = CustomHandler
    
    print("=" * 60)
    print("      DRIVERS SAFETY SYSTEM - PHONE GPS MOBILE GATEWAY")
    print("=" * 60)
    print("\nHow to connect your phone:")
    print("1. Make sure your Phone and PC are on the same Wi-Fi network.")
    print("2. Open the browser on your phone (Chrome / Safari).")
    print("3. Enter the following URL in your phone's address bar:")
    print(f"\n    [URL]  http://{local_ip}:{PORT}/phone_gps.html\n")
    print("4. Allow Location permission when requested by the browser.")
    print("5. Tap 'START TRANSMITTING' to stream your location directly to Firebase!")
    print("=" * 60)
    print(f"Starting server on port {PORT}... Press Ctrl+C to stop.")
    
    try:
        with socketserver.TCPServer(("", PORT), handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user.")
    except Exception as e:
        print(f"\n[ERROR] Could not start server: {e}")

if __name__ == "__main__":
    run_server()
