#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "Starting DocuRAG..."
echo

# Install dependencies. Comment out once installed to start faster.
pip install -r ../requirements.txt -q --disable-pip-version-check

# Optional: expose the local server publicly with a Cloudflare Tunnel.
# Install cloudflared, then uncomment:
# cloudflared tunnel --url http://localhost:3000 &

echo "Server: http://localhost:3000"
echo "Press Ctrl+C to stop."
echo

python server.py
