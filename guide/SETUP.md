# Setup

## Requirements

- **Python 3.10+** (uses modern type-hint syntax).
- An **Anthropic API key** for Ask mode (Search mode needs none).

## 1. Install

```bash
pip install -r requirements.txt
```

Using a virtual environment is recommended:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure

Copy the example env file and edit it:

```bash
cp .env.example .env
```

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for Ask mode |
| `APP_NAME` | `DocuRAG` | Shown as the logo and page title |
| `APP_TAGLINE` | `knowledge base` | Small text under the logo |
| `ASK_MODEL` | `claude-haiku-4-5-20251001` | Any current Claude model id |
| `ANSWER_LANGUAGE` | `English` | Injected into the Ask system prompt |
| `KB_PATH` | `./knowledge_base` | Point at your own content folder |
| `HOST` / `PORT` | `127.0.0.1` / `3000` | Bind address |
| `MAX_HISTORY` | `5` | Prior turns sent with each Ask request |
| `ASK_DAILY_LIMIT` | `20` | Questions per user per day |
| `ASK_INPUT_TOKEN_LIMIT` | `200000` | Daily input-token cap per user |
| `ASK_OUTPUT_TOKEN_LIMIT` | `30000` | Daily output-token cap per user |

Defaults live in `app/config.py`; per-user overrides live in the database.

## 3. Create users

From the `app/` directory:

```bash
python manage_users.py create admin --admin      # an admin (sees the dashboard)
python manage_users.py create alice               # a regular user
python manage_users.py generate 10                # 10 users with random passwords
python manage_users.py list                       # show everyone
```

Other commands: `delete`, `setlimit <user> <tokens>`, `setasklimit <user> <questions>`,
`password <user>`.

## 4. Run

```bash
cd app
python server.py
```

Or use the helper scripts (they also install dependencies):

- macOS/Linux: `./start.sh`
- Windows: `start.bat`

Visit **http://localhost:3000**.

## Resetting

- **Wipe all users/usage:** stop the server and delete `app/users.db` (plus
  `users.db-wal` / `users.db-shm`). It's recreated empty on next start.
- **Rebuild the index** after changing articles: `python scripts/build_index.py`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Ask mode is not configured" | `ANTHROPIC_API_KEY` missing/invalid in `.env` |
| Search returns nothing | Run `python scripts/build_index.py`; check `knowledge_base/index.md` exists |
| "Wrong username or password" | Create a user with `manage_users.py` |
| Port already in use | Change `PORT` in `.env` |
