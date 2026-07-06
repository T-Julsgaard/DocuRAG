# Deployment

DocuRAG is a single FastAPI process with a SQLite database — easy to host. The
main thing to add for real use is **HTTPS**, because auth is sent per request.

## Run it as a server

For anything beyond local testing, run under a production ASGI server:

```bash
cd app
uvicorn server:app --host 0.0.0.0 --port 3000 --workers 2
```

> SQLite + WAL handles a small team fine. If you run multiple workers, they share
> the same `users.db` file — keep it on local disk, not a network share.

Keep it alive with a process manager: **systemd**, **pm2**, **supervisor**, or a
container that restarts on exit.

## Expose it to your team (Cloudflare Tunnel)

The simplest way to get HTTPS and a public URL without opening ports:

```bash
# Install cloudflared, then for a quick throwaway URL:
cloudflared tunnel --url http://localhost:3000

# Or a stable named tunnel mapped to your own domain:
cloudflared tunnel login
cloudflared tunnel create docurag
cloudflared tunnel route dns docurag kb.yourcompany.com
cloudflared tunnel run docurag
```

`start.sh` / `start.bat` have commented-out lines to launch the tunnel alongside
the server.

## Other options

- **Reverse proxy** (nginx/Caddy) terminating TLS in front of uvicorn. Pass
  through `/` and `/static`; the app already sends `X-Accel-Buffering: no` for
  streaming, which nginx respects.
- **Container** — a minimal Dockerfile:

  ```dockerfile
  FROM python:3.12-slim
  WORKDIR /srv
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  WORKDIR /srv/app
  CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "3000"]
  ```

  Mount a volume for `app/users.db` so users survive restarts, and pass secrets
  via environment variables instead of baking `.env` into the image.

## Hardening checklist

- [ ] Serve over **HTTPS** (tunnel or proxy) — never plain HTTP on the internet.
- [ ] Set strong passwords; rotate any generated ones after handing them out.
- [ ] Keep `ANTHROPIC_API_KEY` in the environment, not in the image or repo.
- [ ] Set sensible `ASK_DAILY_LIMIT` and token caps so a key can't run away.
- [ ] Back up `users.db` if account history matters.
- [ ] The built-in rate limits (per-IP) are a backstop, not a substitute for auth.
