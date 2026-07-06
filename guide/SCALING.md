# Scaling beyond the embedded index

DocuRAG is deliberately simple: the **entire article index** (titles + summaries)
is embedded into the Ask system prompt, and Search scans that same index in
memory. This is the right call for small/medium knowledge bases — no vector
database, no embedding pipeline, no infrastructure.

## Where the limits are

The constraint is the **index size in the Ask prompt**, not the number of
articles you can store.

| Articles | Rough index size | Status |
|---|---|---|
| up to ~150 | a few KB–tens of KB | Ideal |
| ~150–500 | tens of KB–~100 KB | Fine; watch prompt cost |
| 500–1000+ | 100 KB+ | Works, but every Ask request pays for the whole index |

Two things grow with the index: **input tokens per Ask request** (you re-send the
index each turn) and **time to first token**. Search mode stays fast regardless —
it's just string scoring.

## Cheap wins before re-architecting

1. **Tighten summaries.** The index is built from `summary` fields. One crisp
   sentence per article keeps it small.
2. **Enable prompt caching.** The index sits at the top of a static system
   prompt — a perfect fit for Anthropic prompt caching, which cuts the repeated
   input cost dramatically. (Add a `cache_control` breakpoint after the index in
   `rag.get_ask_system_prompt` / the request in `server.py`.)
3. **Use a router index.** Instead of one flat index, embed a small category
   router and let Claude `read_file` a per-category sub-index first. Trades a tool
   call for a much smaller base prompt.

## When to move to vector search

If you have **thousands** of articles, or documents far longer than a help-center
article, switch retrieval to embeddings:

1. Chunk articles and embed them (any embedding model + a vector store like
   `sqlite-vss`, FAISS, Qdrant, or pgvector).
2. Replace `search_wiki` in `app/rag.py` with a similarity query that returns the
   top-k chunks.
3. Drop the full-index embed from `get_ask_system_prompt`; feed retrieved chunks
   as context instead.

The frontend, auth, limits, dashboard, and the two-mode UX stay exactly the same —
only the retrieval layer in `rag.py` changes. That's the seam this project is
built around.
