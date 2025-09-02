#!/usr/bin/env python3
"""
Simple HTTP server to serve the LoveLush Mini App.
This script serves the mini app for testing purposes.
"""

import http.server
import os
import socketserver
from pathlib import Path

# Configuration
PORT = 8080
DIRECTORY = Path(__file__).parent


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves index.html for all requests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Add CORS headers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        """Handle preflight requests."""
        self.send_response(200)
        self.end_headers()


def run_server():
    """Start the HTTP server."""
    print(f"Starting mini app server at http://localhost:{PORT}")
    print(f"Serving from: {DIRECTORY.absolute()}")
    print(f"Open in browser: http://localhost:{PORT}")
    print("Press Ctrl+C to stop the server")

    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    # Change to the script's directory
    os.chdir(DIRECTORY)
    run_server()
