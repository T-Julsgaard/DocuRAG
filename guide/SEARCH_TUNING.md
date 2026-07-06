# Tuning the search engine

Search mode is pure Python — no LLM, no embeddings. It scores a query against
each article's **title (×4), tags (×1), and summary (×1)**, with extra boosts for
known phrases and matching categories. All the tuning lives in one file:

```
app/search_config.py
```

Edit it, restart the server, and search behaviour changes. No other code needs to
move. Below is what each setting does and how to adapt it.

## The settings

### `STOP_WORDS`
Common words removed from queries before scoring (English defaults provided).
Swap in your language's function words. Removing noise words improves ranking.

### `TECH_TERMS`
Short tokens (under 4 characters) that would normally be discarded but should be
kept — acronyms, product codes, error codes (`api`, `2fa`, `sso`, `e204`, …).

### `SYNONYMS`
A query word also searches its listed alternatives. Add the phrases your users
actually type:

```python
SYNONYMS = {
    "cancel": ["cancellation", "terminate", "unsubscribe"],
    "invoice": ["bill", "receipt"],
}
```

Links are one-directional — add both keys if you want it to work both ways.

### `CATEGORY_BOOST`
When a query word matches, articles whose **path** contains the given fragment
get +2.0. Use it to steer ambiguous queries to the right section:

```python
CATEGORY_BOOST = {
    "refund": ["Billing"],
    "password": ["Account"],
}
```

The fragment is matched against the file path (which includes the category
folder), case-insensitively.

### `KNOWN_PHRASES`
Multi-word phrases that score a big bonus (+8.0) when they appear verbatim in
both the query and an article title. Good for product names and set phrases:
`"two-factor"`, `"single sign-on"`, `"free trial"`.

### `SUFFIXES` / `MIN_STEM`
A light stemmer so `uploading` matches `upload`. List suffixes longest-first.
Empty the tuple to disable stemming (e.g. for a language where it hurts).

## A practical workflow

1. Collect 15–20 real queries your users would type.
2. Run them and see what ranks (quick script):

   ```python
   import rag
   for q in ["forgot my password", "how much is it", "cant log in"]:
       print(q, "->", [r["title"] for r in rag.search_index_entries(q, 3)])
   ```
3. For each miss, decide the cause:
   - Missing word in the article → add a **tag** to the article.
   - User uses a different word → add a **synonym**.
   - Right section, wrong article → add a **category boost**.
4. Re-run. Repeat until the common queries land.

## Tags vs. synonyms — which?

- A **tag** lives on one article and only helps that article.
- A **synonym** is global and helps every article that contains the target word.

Use tags for article-specific phrasing; use synonyms for vocabulary that recurs
across the whole knowledge base.
