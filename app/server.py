import sys
import io
import json
import time
from typing import Generator

# Make the Windows console emit UTF-8 instead of cp1252.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

try:
    from anthropic import Anthropic
    _anthropic_available = True
except ImportError:
    _anthropic_available = False
    print("[WARN] The 'anthropic' package is not installed — Ask mode is disabled.")

from config import (
    ASK_MODEL, PORT, HOST, MAX_HISTORY, DB_PATH, APP_NAME, APP_TAGLINE,
    MAX_ASK_ITERATIONS,
)
from rag import (
    get_ask_system_prompt, read_wiki_file, search_wiki,
    search_index_entries, _load_index_entries, get_image_path,
)
from tools import TOOLS
from database import (
    init_db, authenticate, get_today_usage,
    all_users_with_usage, create_user, delete_user, update_limit,
    get_ask_status, record_ask_question, add_ask_tokens, log_event, get_dashboard_data,
)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=APP_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Anthropic() reads ANTHROPIC_API_KEY from the environment. If the key is
# missing we keep the server running for Search mode and just disable Ask.
anthropic_client = None
if _anthropic_available:
    try:
        anthropic_client = Anthropic()
    except Exception:
        print("[WARN] ANTHROPIC_API_KEY not set — Ask mode disabled, Search mode still works.")

# Built once at startup (Search mode uses no LLM).
ASK_SYSTEM_PROMPT = get_ask_system_prompt()

print("Loading search index...", end=" ", flush=True)
_entries = _load_index_entries()
print(f"{len(_entries)} articles ready.")

BASE_DIR = Path(__file__).parent
init_db(DB_PATH)


# --- Request models ---

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    username: str = ""
    password: str = ""
    mode: str = "search"  # "search" or "ask"

class AuthRequest(BaseModel):
    username: str = ""
    password: str = ""

class AdminBase(BaseModel):
    admin_username: str
    admin_password: str

class CreateUserRequest(AdminBase):
    username: str
    password: str
    daily_token_limit: int = 1_000_000
    is_admin: bool = False

class UpdateLimitRequest(AdminBase):
    daily_token_limit: int


# --- Auth helpers ---

def require_auth(username: str, password: str):
    user = authenticate(DB_PATH, username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Wrong username or password")
    return user

def require_admin(admin_username: str, admin_password: str):
    user = require_auth(admin_username, admin_password)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# --- Shared tool runner ---

def run_tool(name: str, inputs: dict, already_read: set[str] | None = None) -> str:
    if name == "read_file":
        path = inputs["path"]
        norm = path.replace("\\", "/").lower()
        if already_read is not None and norm in already_read:
            return "(Already read — the content is in your context.)"
        return read_wiki_file(path)
    if name == "search_wiki":
        return search_wiki(inputs["query"])
    return f"Unknown tool: {name}"


# --- Search mode: server-side keyword search, no LLM ---

def stream_search_loop(message: str, user_id: int) -> Generator[str, None, None]:
    print(f"\n-> [SEARCH] {message[:80]}")
    try:
        results = search_index_entries(message, max_results=8)

        def _format(r: dict, idx: int) -> str:
            title, summary, url = r["title"], r["summary"], r.get("url", "")
            title_part = f"[{title}]({url})" if url else f"**{title}**"
            return f"{idx}. {title_part} — {summary}"

        if results:
            lines = ["**Relevant articles:**\n"]
            lines += [_format(r, i) for i, r in enumerate(results, 1)]
            text = "\n".join(lines)
        else:
            text = "No relevant articles found. Try different keywords."

        print(f"  -> {len(results)} results")
        yield f"data: {json.dumps({'type': 'token', 'text': text}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'files_read': [], 'tokens_used': 0}, ensure_ascii=False)}\n\n"
    except Exception as e:
        print(f"[ERROR] stream_search_loop: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': 'Internal server error'}, ensure_ascii=False)}\n\n"


# --- Ask mode: Anthropic Claude, full agentic RAG loop ---

def stream_ask_loop(message: str, history: list[Message], username: str = "", user_id: int = 0) -> Generator[str, None, None]:
    if not anthropic_client:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Ask mode is not configured (missing ANTHROPIC_API_KEY)'}, ensure_ascii=False)}\n\n"
        return

    history_slice = history[-(MAX_HISTORY * 2):]
    messages = [{"role": m.role, "content": m.content} for m in history_slice]
    messages.append({"role": "user", "content": message})

    files_read: list[str] = []
    already_read: set[str] = set()
    total_in = 0
    total_out = 0
    final_response = ""

    print(f"\n-> [ASK] {message[:80]}")

    try:
        for i in range(MAX_ASK_ITERATIONS):
            tools_this_turn = TOOLS if i < MAX_ASK_ITERATIONS - 1 else []
            force_answer = i == MAX_ASK_ITERATIONS - 1

            if force_answer:
                messages.append({
                    "role": "user",
                    "content": "Answer now using the articles you have already read. Do not call any more tools.",
                })

            kwargs = {
                "model": ASK_MODEL,
                "system": ASK_SYSTEM_PROMPT,
                "messages": messages,
                "max_tokens": 16384,
            }
            if tools_this_turn:
                kwargs["tools"] = tools_this_turn

            turn_text_buf: list[str] = []

            # Retry with exponential backoff on rate limits (max 3 attempts).
            final = None
            for attempt in range(3):
                try:
                    with anthropic_client.messages.stream(**kwargs) as stream:
                        for event in stream:
                            if (event.type == "content_block_delta"
                                    and hasattr(event.delta, "type")
                                    and event.delta.type == "text_delta"):
                                turn_text_buf.append(event.delta.text)
                        final = stream.get_final_message()
                    break
                except Exception as e:
                    turn_text_buf.clear()
                    is_rate_limit = "rate_limit" in str(e).lower() or "429" in str(e)
                    if is_rate_limit and attempt < 2:
                        wait = 30 * (2 ** attempt)  # 30s, 60s
                        print(f"  [RATE LIMIT] waiting {wait}s (attempt {attempt+1}/3)...")
                        yield f"data: {json.dumps({'type': 'status', 'message': f'Rate limit — waiting {wait} seconds...'}, ensure_ascii=False)}\n\n"
                        time.sleep(wait)
                    else:
                        raise
            if final is None:
                raise RuntimeError("No response from Anthropic after retries")

            turn_text = "".join(turn_text_buf)

            out_tokens = getattr(final.usage, "output_tokens", 0)
            total_in = getattr(final.usage, "input_tokens", 0)
            total_out += out_tokens
            print(f"  iter {i+1}: stop={final.stop_reason} out_tokens={out_tokens}")

            # Rebuild the assistant message manually — model_dump() may carry
            # internal fields the API rejects on the next turn.
            assistant_content = []
            for block in final.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                else:
                    assistant_content.append(block.model_dump())
            messages.append({"role": "assistant", "content": assistant_content})

            if final.stop_reason != "tool_use":
                final_response = turn_text
                yield f"data: {json.dumps({'type': 'thinking_clear'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'commit_stream', 'text': turn_text}, ensure_ascii=False)}\n\n"
                print(f"  -> answer generated, files: {files_read}")
                yield f"data: {json.dumps({'type': 'done', 'files_read': files_read, 'input_tokens': total_in, 'output_tokens': total_out}, ensure_ascii=False)}\n\n"
                try:
                    add_ask_tokens(DB_PATH, user_id, total_in, total_out)
                    log_event(DB_PATH, "ask", username=username or None,
                              query=message[:500], response=final_response[:2000],
                              tokens_input=total_in, tokens_output=total_out)
                except Exception:
                    pass
                return

            # Reasoning turn — surface any text as a thinking block.
            if turn_text.strip():
                yield f"data: {json.dumps({'type': 'promote_to_thinking', 'text': turn_text}, ensure_ascii=False)}\n\n"

            # Run the tool calls.
            tool_results = []
            for block in final.content:
                if block.type == "tool_use":
                    args = block.input
                    if block.name == "read_file":
                        path = args.get("path", "")
                        files_read.append(path)
                        filename = path.split("/")[-1].replace(".md", "")
                        yield f"data: {json.dumps({'type': 'tool_activity', 'text': f'Reading: {filename}'}, ensure_ascii=False)}\n\n"
                    print(f"    tool: {block.name}({args})")
                    result = run_tool(block.name, args, already_read)
                    if block.name == "read_file":
                        already_read.add(args.get("path", "").replace("\\", "/").lower())
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

        # Iteration cap reached.
        yield f"data: {json.dumps({'type': 'done', 'files_read': files_read, 'input_tokens': total_in, 'output_tokens': total_out}, ensure_ascii=False)}\n\n"
        try:
            add_ask_tokens(DB_PATH, user_id, total_in, total_out)
            log_event(DB_PATH, "ask", username=username or None,
                      query=message[:500], response=final_response[:2000],
                      tokens_input=total_in, tokens_output=total_out)
        except Exception:
            pass

    except Exception as e:
        print(f"[ERROR] stream_ask_loop: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': 'Internal server error'}, ensure_ascii=False)}\n\n"


# --- Endpoints ---

@app.post("/chat")
@limiter.limit("15/minute")
def chat(request: Request, req: ChatRequest):
    user = require_auth(req.username, req.password)
    mode = req.mode.lower()

    if mode == "ask":
        if not _anthropic_available:
            raise HTTPException(status_code=503, detail="Ask mode unavailable (anthropic package missing)")

        status = get_ask_status(DB_PATH, user["id"])
        if not status["can_ask"]:
            if status["remaining"] == 0:
                msg = f"You have used all {status['daily_limit']} questions for today."
            elif status["tokens_in_today"] >= status["daily_input_limit"]:
                msg = f"Daily input token limit reached ({status['daily_input_limit']:,} tokens)."
            elif status["tokens_out_today"] >= status["daily_output_limit"]:
                msg = f"Daily output token limit reached ({status['daily_output_limit']:,} tokens)."
            else:
                msg = "Daily limit reached."
            raise HTTPException(status_code=429, detail={"reason": "daily_limit", "message": msg})

        record_ask_question(DB_PATH, user["id"])
        return StreamingResponse(
            stream_ask_loop(req.message, req.history, username=user["username"], user_id=user["id"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Search mode (default)
    today_usage = get_today_usage(DB_PATH, user["id"])
    if today_usage >= user["daily_token_limit"]:
        raise HTTPException(
            status_code=429,
            detail=f"Daily token limit reached ({user['daily_token_limit']:,} tokens). Try again tomorrow."
        )

    return StreamingResponse(
        stream_search_loop(req.message, user["id"]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/verify-password")
@limiter.limit("5/minute")
def verify_password(request: Request, req: AuthRequest):
    user = authenticate(DB_PATH, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Wrong username or password")
    return {"ok": True, "is_admin": bool(user["is_admin"])}


@app.get("/app-config")
def app_config():
    """Branding the frontend reads at load time — set APP_NAME / APP_TAGLINE in .env."""
    return {"app_name": APP_NAME, "tagline": APP_TAGLINE}


@app.get("/ask-status")
@limiter.limit("30/minute")
def ask_status_endpoint(request: Request, username: str, password: str):
    user = require_auth(username, password)
    return get_ask_status(DB_PATH, user["id"])


@app.get("/auth-status")
def auth_status():
    return {"password_required": True}


@app.get("/search")
@limiter.limit("60/minute")
def search_endpoint(request: Request, q: str, username: str, password: str):
    require_auth(username, password)
    q = q.strip()
    if not q:
        return {"results": [], "count": 0}

    results = search_index_entries(q, max_results=5)

    for r in results:
        norm = r["path"].replace("\\", "/")
        parts = norm.split("/")
        try:
            idx = next(i for i, p in enumerate(parts) if p == "articles")
            r["category"] = parts[idx + 1] if idx + 1 < len(parts) else ""
        except StopIteration:
            r["category"] = ""
        r.pop("tags", None)  # tags are server-side search hints only

    try:
        log_event(DB_PATH, "search", username=username, query=q[:500])
    except Exception:
        pass

    return {"results": results, "count": len(results)}


# --- Admin endpoints ---

@app.get("/admin/dashboard-data")
@limiter.limit("30/minute")
def dashboard_data_endpoint(request: Request, admin_username: str, admin_password: str, days: int = 30):
    require_admin(admin_username, admin_password)
    return get_dashboard_data(DB_PATH, days)


@app.get("/admin/users")
@limiter.limit("30/minute")
def admin_list_users(request: Request, admin_username: str, admin_password: str):
    require_admin(admin_username, admin_password)
    users = all_users_with_usage(DB_PATH)
    for u in users:
        u.pop("password_hash", None)
    return users


@app.post("/admin/users")
@limiter.limit("30/minute")
def admin_create_user(request: Request, req: CreateUserRequest):
    require_admin(req.admin_username, req.admin_password)
    from database import get_user
    if get_user(DB_PATH, req.username):
        raise HTTPException(status_code=409, detail=f"User '{req.username}' already exists")
    create_user(DB_PATH, req.username, req.password, req.daily_token_limit, req.is_admin)
    return {"ok": True, "username": req.username}


@app.delete("/admin/users/{username}")
@limiter.limit("30/minute")
def admin_delete_user(request: Request, username: str, req: AdminBase):
    require_admin(req.admin_username, req.admin_password)
    delete_user(DB_PATH, username)
    return {"ok": True}


@app.put("/admin/users/{username}/limit")
@limiter.limit("30/minute")
def admin_update_limit(request: Request, username: str, req: UpdateLimitRequest):
    require_admin(req.admin_username, req.admin_password)
    update_limit(DB_PATH, username, req.daily_token_limit)
    return {"ok": True}


# --- Static files ---

@app.get("/")
def root():
    return FileResponse(BASE_DIR / "static" / "index.html")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/i/{short_id}")
def serve_image(short_id: str):
    """Serve a knowledge-base image by its 8-char id (see rag._convert_images)."""
    path = get_image_path(short_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(path))


if __name__ == "__main__":
    import uvicorn
    print(f"Starting {APP_NAME} on http://{HOST}:{PORT}")
    print(f"Search mode: server-side keyword search (no LLM)")
    print(f"Ask model:   {ASK_MODEL}")
    print(f"Database:    {DB_PATH}")
    uvicorn.run(app, host=HOST, port=PORT, reload=False)
