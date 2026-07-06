"""
Retrieval engine.

Two retrieval paths share one knowledge base:

  * Search mode  — pure server-side keyword scoring over the flat index
                   (titles + summaries). No LLM, instant, free.
  * Ask mode     — the index is embedded into the system prompt and Claude
                   navigates it agentically with the read_file / search_wiki
                   tools (see server.py).

All language/domain tuning lives in search_config.py.
"""

import math
import re
import hashlib
from pathlib import Path

from config import (
    KB_ROOT, ARTICLES_PATH, INDEX_PATH, INSTRUCTIONS_PATH,
    APP_NAME, ANSWER_LANGUAGE,
)
from search_config import (
    STOP_WORDS, TECH_TERMS, SYNONYMS, CATEGORY_BOOST,
    KNOWN_PHRASES, SUFFIXES, MIN_STEM,
)

# --- Module caches (built once on first use) ---
_INDEX_ENTRIES: list[dict] | None = None
_URL_MAP: dict[str, str] | None = None
_IMAGE_MAP: dict[str, Path] | None = None


# ---------------------------------------------------------------------------
# Light stemming
# ---------------------------------------------------------------------------
def _stem(word: str) -> str:
    """Strip the longest matching suffix, keeping at least MIN_STEM chars."""
    for suffix in SUFFIXES:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if len(stem) >= MIN_STEM:
                return stem
    return word


# ---------------------------------------------------------------------------
# Images: Obsidian-style ![[file.png]] embeds -> short, token-cheap /i/<id> URLs
# ---------------------------------------------------------------------------
def _image_short_id(path: Path) -> str:
    """Stable 8-char id derived from the absolute path."""
    return hashlib.md5(str(path.resolve()).encode("utf-8")).hexdigest()[:8]


def _build_image_map() -> dict[str, Path]:
    """Scan every _assets folder once and map short_id -> Path. Cached."""
    global _IMAGE_MAP
    if _IMAGE_MAP is not None:
        return _IMAGE_MAP
    image_map: dict[str, Path] = {}
    for assets_dir in KB_ROOT.rglob("_assets"):
        if not assets_dir.is_dir():
            continue
        for img in assets_dir.iterdir():
            if img.is_file():
                image_map[_image_short_id(img)] = img
    _IMAGE_MAP = image_map
    return image_map


def get_image_path(short_id: str) -> Path | None:
    return _build_image_map().get(short_id)


# ---------------------------------------------------------------------------
# Index loading
# ---------------------------------------------------------------------------
def _load_url_map() -> dict[str, str]:
    """Map article path -> external `url:` from frontmatter, if present. Cached.

    Lets Search mode link straight to a canonical source (e.g. a help-center
    article) instead of the local file. Optional — articles without a url
    simply show as plain titles.
    """
    global _URL_MAP
    if _URL_MAP is not None:
        return _URL_MAP

    url_map: dict[str, str] = {}
    url_pattern = re.compile(r'^url:\s*"?([^"\n]+)"?', re.MULTILINE)

    for filepath in ARTICLES_PATH.rglob("*.md"):
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")[:2000]
            m = url_pattern.search(content)
            if m:
                rel_path = str(filepath.relative_to(KB_ROOT)).replace("\\", "/")
                url_map[rel_path] = m.group(1).strip()
        except Exception:
            pass

    _URL_MAP = url_map
    return url_map


def _load_index_entries() -> list[dict]:
    """Parse index.md into [{path, title, summary, tags, url}]. Cached.

    Index lines look like:
        - `articles/billing/refunds.md` — How refunds work | refund, credit
    The part after " | " is optional search-only tags.
    """
    global _INDEX_ENTRIES
    if _INDEX_ENTRIES is not None:
        return _INDEX_ENTRIES

    entries: list[dict] = []
    if not INDEX_PATH.exists():
        _INDEX_ENTRIES = entries
        return entries

    url_map = _load_url_map()
    pattern = re.compile(r"^- `([^`]+\.md)`\s*[—–-]\s*(.+)$")

    for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        path = m.group(1)
        raw = m.group(2).strip()
        if " | " in raw:
            summary, tags_str = raw.split(" | ", 1)
            summary = summary.strip()
        else:
            summary, tags_str = raw, ""
        stem = Path(path).stem
        words = stem.replace("_", " ").replace("-", " ").split()
        # Title-case for display, but leave all-caps/with-digit tokens (acronyms,
        # product codes like "2FA", "API") untouched.
        title = " ".join(w if (w.isupper() or any(c.isdigit() for c in w)) else w.capitalize()
                          for w in words).strip()
        norm_path = path.replace("\\", "/")
        entries.append({
            "path": path,
            "title": title,
            "summary": summary,
            "tags": tags_str,
            "url": url_map.get(norm_path, ""),
        })

    _INDEX_ENTRIES = entries
    return entries


# ---------------------------------------------------------------------------
# Query processing
# ---------------------------------------------------------------------------
def _extract_keywords(query: str) -> list[str]:
    """Drop stop-words and very short tokens (acronyms in TECH_TERMS survive)."""
    words = re.split(r"[\s,?.!:;()\[\]/]+", query.lower())
    result = []
    for w in words:
        if not w or w in STOP_WORDS:
            continue
        if w in TECH_TERMS or len(w) >= 4:
            result.append(w)
    return result


def _keyword_variants(kw: str) -> list[str]:
    """Expand a keyword into stem + synonyms (+ a prefix-trim safety net)."""
    variants: list[str] = [kw]

    stem = _stem(kw)
    if stem != kw and stem not in variants:
        variants.append(stem)

    if len(kw) >= 6 and kw[:-2] not in variants:
        variants.append(kw[:-2])
    if len(kw) >= 8 and kw[:-3] not in variants:
        variants.append(kw[:-3])

    for syn in SYNONYMS.get(kw, []):
        if syn not in variants:
            variants.append(syn)
        syn_stem = _stem(syn)
        if syn_stem != syn and syn_stem not in variants:
            variants.append(syn_stem)

    return variants


def _category_boost(entry: dict, keywords: list[str]) -> float:
    """+2.0 per keyword whose CATEGORY_BOOST fragment is in the article path."""
    path_l = entry["path"].replace("\\", "/").lower()
    boost = 0.0
    for kw in keywords:
        for cat_fragment in CATEGORY_BOOST.get(kw, []):
            if cat_fragment.lower() in path_l:
                boost += 2.0
                break
    return boost


def _score_entry(entry: dict, keywords: list[str], query_lower: str = "") -> tuple[float, int]:
    """Score one article. Title hit = 4x, summary/tag hit = 1x.

    Known phrases in the title add 8.0; category matches add via _category_boost.
    Returns (score, matched_keyword_count).
    """
    title_l = entry["title"].lower()
    summary_l = entry["summary"].lower()
    tags_l = entry.get("tags", "").lower()
    score = 0.0
    matched = 0

    if query_lower:
        for phrase in KNOWN_PHRASES:
            if phrase in query_lower and phrase in title_l:
                score += 8.0

    score += _category_boost(entry, keywords)

    for kw in keywords:
        hit = False
        for variant in _keyword_variants(kw):
            if variant in title_l:
                score += 4.0
                hit = True
                break
            elif variant in tags_l:
                score += 1.0
                hit = True
                break
            elif variant in summary_l:
                score += 1.0
                hit = True
                break
        if hit:
            matched += 1
    return (score, matched) if matched > 0 else (0.0, 0)


def search_index_entries(
    query: str,
    max_results: int = 5,
    min_score: float = 2.0,
) -> list[dict]:
    """Rank index entries against a query.

    Phase 1: score titles + summaries from the flat index.
    Phase 2: if fewer than 3 hits, fall back to full-text search of article
             bodies (search_wiki) to surface buried matches.
    """
    keywords = _extract_keywords(query)
    if not keywords:
        return []

    # Allow one missed keyword — the score threshold filters weak hits.
    required_matches = max(1, len(keywords) - 1)

    entries = _load_index_entries()
    query_lower = query.lower()

    scored: list[tuple[float, dict]] = []
    for entry in entries:
        score, matched = _score_entry(entry, keywords, query_lower)
        if score >= min_score and matched >= required_matches:
            scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    results = [e for _, e in scored[:max_results]]

    # Phase 2 — full-text fallback
    if len(results) < 3:
        specific = sorted(keywords, key=len, reverse=True)[:2]
        content_query = " ".join(specific)
        content_paths = set()
        for line in search_wiki(content_query).splitlines():
            line = line.strip()
            if line and not line.startswith("No "):
                content_paths.add(line.replace("\\", "/"))

        existing = {r["path"] for r in results}
        entry_map = {e["path"].replace("\\", "/"): e for e in entries}
        for cp in list(content_paths)[:4]:
            if cp not in existing:
                entry = entry_map.get(cp)
                if entry:
                    results.append(entry)

    return results[:max_results]


# ---------------------------------------------------------------------------
# System prompt for Ask mode
# ---------------------------------------------------------------------------
def _load_instructions() -> str:
    if INSTRUCTIONS_PATH.exists():
        return INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    # Minimal built-in fallback so the app still answers without an instructions file.
    return (
        f"You are a helpful assistant for the {APP_NAME} knowledge base. "
        f"Answer in {ANSWER_LANGUAGE}. Use the read_file and search_wiki tools to "
        f"ground every answer in the articles. Never invent facts."
    )


def get_ask_system_prompt() -> str:
    """Instructions + the full article index, embedded once at startup.

    For small/medium knowledge bases (up to a few hundred articles) embedding
    the whole index is simplest and cheapest — Claude sees every title/summary
    in one shot and reads only the articles it needs.
    """
    instructions = _load_instructions()
    index_text = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""
    lang_line = f"\n\nAlways answer in {ANSWER_LANGUAGE}."
    return (
        f"{instructions}{lang_line}\n\n---\n\n"
        f"# Full article index\n\n"
        f"Find the relevant article(s) by summary, then read them with `read_file`.\n\n"
        f"{index_text}"
    )


# ---------------------------------------------------------------------------
# Tools exposed to the model
# ---------------------------------------------------------------------------
def _convert_images(content: str, article_path: Path) -> str:
    """Rewrite ![[image.ext]] embeds to short ![](/i/<id>) URLs served by /i/."""
    image_map = _build_image_map()
    assets_dir = article_path.parent / "_assets"

    def replace(m: re.Match) -> str:
        filename = m.group(1)
        candidate = assets_dir / filename
        if candidate.is_file():
            sid = _image_short_id(candidate)
            image_map.setdefault(sid, candidate)
            return f"![](/i/{sid})"
        return f"*[image: {filename}]*"

    return re.sub(r'!\[\[([^\]]+)\]\]', replace, content)


def read_wiki_file(path: str) -> str:
    """Read one article relative to the knowledge-base root. Used by the LLM.

    Path traversal is blocked — the resolved file must stay inside KB_ROOT.
    """
    kb_root = KB_ROOT.resolve()
    candidate = (KB_ROOT / path)
    try:
        full_path = candidate.resolve()
        full_path.relative_to(kb_root)
        if full_path.is_file():
            content = full_path.read_text(encoding="utf-8")
            return _convert_images(content, full_path)
    except (ValueError, Exception):
        pass
    return f"File not found: {path}"


def search_wiki(query: str, max_results: int = 10) -> str:
    """BM25-flavoured full-text keyword search across all article bodies.

    Scores each keyword by term frequency (log-damped); requires at least half
    the keywords to be present. Returns ranked relative paths.
    """
    keywords = [k.lower() for k in query.split() if k.strip()]
    if not keywords:
        return "Empty query."

    scored: list[tuple[float, str]] = []
    for filepath in ARTICLES_PATH.rglob("*.md"):
        try:
            content_lower = filepath.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue

        doc_score = 0.0
        hits = 0
        for kw in keywords:
            count = content_lower.count(kw)
            if count > 0:
                doc_score += 1 + math.log(count)
                hits += 1

        required = max(1, (len(keywords) + 1) // 2)
        if hits >= required:
            rel_path = str(filepath.relative_to(KB_ROOT)).replace("\\", "/")
            scored.append((doc_score, rel_path))

    scored.sort(key=lambda x: -x[0])
    results = [path for _, path in scored[:max_results]]
    return "\n".join(results) if results else "No results found for the query."
