#!/usr/bin/env python3
"""
Build the static GitHub Pages preview into ./docs.

The preview is a *self-contained* copy of the frontend that runs with **no
backend, no API key, and no login**. It's the public "shop window": Search
runs entirely client-side over a pre-built index, and Ask returns a handful of
canned demo answers so visitors can see what a grounded response looks like.

How it stays clean:
  * app/ is never modified — the frontend is copied as-is into docs/.
  * A small preview-shim.js (loaded before app.js) intercepts window.fetch and
    answers the backend routes locally. app.js has no idea it isn't talking to
    a real server.
  * All /static/ absolute paths are rewritten to relative so the site works
    from a project subpath (e.g. https://user.github.io/DocuRAG/).

Run it from anywhere:
    python scripts/build_preview.py

Then point GitHub Pages at the /docs folder on your default branch.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_STATIC = ROOT / "app" / "static"
PREVIEW_SRC = ROOT / "preview"
DOCS = ROOT / "docs"
DATA = DOCS / "data"

# Import the real app's config + retrieval so the exported index and search
# tuning stay perfectly in sync with the backend — single source of truth.
sys.path.insert(0, str(ROOT / "app"))
import rag  # noqa: E402
from config import KB_ROOT, APP_NAME, APP_TAGLINE  # noqa: E402
import search_config as sc  # noqa: E402


def category_of(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if "articles" in parts:
        i = parts.index("articles")
        if i + 1 < len(parts):
            return parts[i + 1]
    return ""


def build_search_index() -> dict:
    """Export index entries + search tuning as JSON for the client-side engine."""
    entries = []
    for e in rag._load_index_entries():
        path = e["path"]
        body = ""
        try:
            body = (KB_ROOT / path).read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            pass
        entries.append({
            "path": path,
            "title": e["title"],
            "summary": e["summary"],
            "tags": e.get("tags", ""),
            "url": e.get("url", ""),
            "category": category_of(path),
            "text": body,  # lowercased body — powers the full-text fallback
        })

    config = {
        "STOP_WORDS": sorted(sc.STOP_WORDS),
        "TECH_TERMS": sorted(sc.TECH_TERMS),
        "SYNONYMS": sc.SYNONYMS,
        "CATEGORY_BOOST": sc.CATEGORY_BOOST,
        "KNOWN_PHRASES": sorted(sc.KNOWN_PHRASES),
        "SUFFIXES": list(sc.SUFFIXES),  # order matters — keep as-is
        "MIN_STEM": sc.MIN_STEM,
    }
    return {"config": config, "entries": entries}


def patch_index_html(html: str) -> str:
    """Rewrite absolute /static/ paths to relative and inject the preview shim."""
    html = html.replace('href="/static/style.css?v=1"', 'href="style.css?v=1"')
    html = html.replace('href="/static/favicon.svg"', 'href="favicon.svg"')
    html = html.replace('src="/static/app.js?v=1"', 'src="app.js?v=1"')
    # Load the shim BEFORE app.js so window.fetch is patched and creds seeded
    # before app.js runs its auto-login.
    html = html.replace(
        '<script src="app.js?v=1"></script>',
        '<script src="preview-shim.js"></script>\n'
        '    <script src="app.js?v=1"></script>',
    )
    return html


def main() -> None:
    if not PREVIEW_SRC.exists():
        sys.exit(f"Missing preview source dir: {PREVIEW_SRC}")

    # Fresh build
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DATA.mkdir(parents=True)

    # 1. Copy the frontend as-is (flattened out of /static)
    for name in ("app.js", "style.css", "favicon.svg"):
        shutil.copy2(APP_STATIC / name, DOCS / name)

    # 2. Patched HTML
    html = (APP_STATIC / "index.html").read_text(encoding="utf-8")
    (DOCS / "index.html").write_text(patch_index_html(html), encoding="utf-8")

    # 3. Preview shim
    shutil.copy2(PREVIEW_SRC / "preview-shim.js", DOCS / "preview-shim.js")

    # 4. Data files
    (DATA / "search-index.json").write_text(
        json.dumps(build_search_index(), ensure_ascii=False), encoding="utf-8")
    shutil.copy2(PREVIEW_SRC / "demo-answers.json", DATA / "demo-answers.json")
    (DATA / "app-config.json").write_text(
        json.dumps({"app_name": APP_NAME, "tagline": APP_TAGLINE}, ensure_ascii=False),
        encoding="utf-8")

    # 5. Disable Jekyll processing on GitHub Pages
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    n = len(json.loads((DATA / "search-index.json").read_text(encoding="utf-8"))["entries"])
    print(f"Built preview -> {DOCS}")
    print(f"  {n} articles indexed for client-side search")
    print(f"  Serve locally:  python -m http.server -d docs 8000")
    print(f"  GitHub Pages :  Settings -> Pages -> Deploy from branch -> /docs")


if __name__ == "__main__":
    main()
