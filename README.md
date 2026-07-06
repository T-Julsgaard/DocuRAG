# DocuRAG

A plug-and-play **RAG knowledge base** for small and mid-size document sets. Point
it at a folder of markdown articles and you get a clean chat UI with two modes:

- **🔍 Search** — instant, server-side keyword search. No LLM, no API cost, no rate limits.
- **💬 Ask** — an agentic RAG assistant (Anthropic Claude) that reads your articles and answers grounded questions, with sources.

It ships with user accounts, per-user daily limits, an admin usage dashboard, and a small demo knowledge base so it runs the moment you clone it.

<!-- Add a screenshot here once you've run it: ![DocuRAG](docs/screenshot.png) -->

## Why DocuRAG

- **Two retrieval paths, one knowledge base.** Free keyword search for everyday lookups; LLM answers when someone needs a real explanation. You control the cost.
- **Markdown-native.** Articles are plain `.md` files with a little YAML frontmatter. Works great with Obsidian, Git, or any editor.
- **Cheap by design.** The whole article index is embedded into the Ask prompt once, so Claude reads only the handful of articles it actually needs.
- **Self-hostable.** One Python process + SQLite. No vector database to run.
- **Tunable without code.** Stop-words, synonyms, and category boosts live in one config file.

> Best suited for **up to a few hundred articles**. Beyond that, you'd want a vector store — see [guide/SCALING.md](guide/SCALING.md).

## Quick start

```bash
# 1. Clone and enter the project
git clone <your-repo-url> docurag && cd docurag

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env          # then edit .env and add your ANTHROPIC_API_KEY

# 4. Create an admin user
cd app
python manage_users.py create admin --admin

# 5. Run
python server.py              # or: ./start.sh  (Windows: start.bat)
```

Open **http://localhost:3000**, log in, and try both modes against the bundled
demo (a fictional product called *Nimbus*).

> **Search** mode works with no API key at all. **Ask** mode needs `ANTHROPIC_API_KEY` in `.env`.

## Make it yours

1. **Branding** — set `APP_NAME` and `APP_TAGLINE` in `.env`.
2. **Content** — replace everything in `knowledge_base/articles/` with your own
   markdown, then rebuild the index:
   ```bash
   python scripts/build_index.py
   ```
   See [guide/AUTHORING.md](guide/AUTHORING.md) for the article format.
3. **Assistant behaviour** — edit `knowledge_base/instructions.md` (the Ask-mode
   system prompt) for your product, tone, and answer language.
4. **Search tuning** — edit `app/search_config.py` to teach the keyword engine
   your synonyms and categories. See [guide/SEARCH_TUNING.md](guide/SEARCH_TUNING.md).

## How it works

```
        ┌─────────────┐         Search mode: pure Python keyword scoring
        │   Browser   │  ───►   over knowledge_base/index.md   (no LLM)
        │  (chat UI)  │
        └─────────────┘         Ask mode: Claude + read_file / search_wiki
              │                  tools, grounded in your articles
              ▼
        ┌─────────────┐   ┌──────────────────────────────┐
        │  server.py  │──►│ knowledge_base/articles/*.md │
        │  (FastAPI)  │   │ knowledge_base/index.md       │
        └─────────────┘   └──────────────────────────────┘
              │
              ▼  users, limits, usage log
          users.db (SQLite)
```

| Path | What it is |
|---|---|
| `app/server.py` | FastAPI app: endpoints, both retrieval modes, streaming |
| `app/rag.py` | Retrieval engine (keyword scoring + Ask-mode tools) |
| `app/search_config.py` | Language/domain tuning — **edit this for your content** |
| `app/database.py` | SQLite users, limits, and usage logging |
| `app/manage_users.py` | CLI to create/list/delete users and set limits |
| `app/static/` | Frontend (vanilla JS, no build step) |
| `knowledge_base/` | Your articles, the generated index, and the Ask prompt |
| `scripts/build_index.py` | Regenerates `index.md` from your articles |
| `guide/` | Setup, authoring, tuning, deployment, scaling guides |
| `preview/`, `scripts/build_preview.py` | Source for the static GitHub Pages demo |
| `docs/` | Generated static demo site (built by `build_preview.py`) — do not edit by hand |

## Documentation

- [guide/SETUP.md](guide/SETUP.md) — detailed setup and configuration
- [guide/AUTHORING.md](guide/AUTHORING.md) — writing articles and the frontmatter format
- [guide/SEARCH_TUNING.md](guide/SEARCH_TUNING.md) — tuning the keyword engine
- [guide/DEPLOYMENT.md](guide/DEPLOYMENT.md) — exposing it to your team
- [guide/SCALING.md](guide/SCALING.md) — when and how to grow past the embedded-index approach

## Security notes

- Passwords are hashed with PBKDF2-HMAC-SHA256. `.env`, `*.db`, and generated
  credentials are git-ignored.
- Auth is username/password sent per request — fine behind a tunnel for an
  internal team, but **put it behind HTTPS** (e.g. a Cloudflare Tunnel) before
  exposing it. See [guide/DEPLOYMENT.md](guide/DEPLOYMENT.md).

## License

MIT — see [LICENSE](LICENSE).
