@echo off
cd /d "%~dp0"

echo Starting DocuRAG...
echo.

REM Install dependencies (quiet). Comment out once installed to start faster.
pip install -r ../requirements.txt -q --no-input --disable-pip-version-check 2>nul

REM Optional: expose the local server publicly with a Cloudflare Tunnel.
REM Install cloudflared, then uncomment one of the lines below.
REM start "Cloudflare Tunnel" cloudflared tunnel --url http://localhost:3000

echo Server: http://localhost:3000
echo Press Ctrl+C to stop.
echo.

python server.py
pause
