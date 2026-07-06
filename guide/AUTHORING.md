# Authoring articles

Articles are plain markdown files under `knowledge_base/articles/`. Folder names
become categories. After adding or editing articles, rebuild the index:

```bash
python scripts/build_index.py
```

## Frontmatter

Every article starts with a small YAML block:

```markdown
---
summary: "One sentence describing what this article covers and when to use it."
category: "Billing"
tags: "refund, money back, chargeback"
url: "https://help.example.com/billing/refunds"
---

# Article title

Body in markdown...
```

| Field | Required | Purpose |
|---|---|---|
| `summary` | **Yes** | Shown in search results and in the Ask index. This is what both modes match against — make it specific. |
| `category` | No | Groups the article. Use `"Parent / Child"` for a sub-category. Defaults to the folder, then `Uncategorized`. |
| `tags` | No | Extra keywords for Search mode only. Great for synonyms and customer phrasing. Not shown to users. |
| `url` | No | Canonical link. Search results and Ask sources link here. Omit for local-only content. |

## How the two modes use articles

- **Search** scores the query against each article's **title, summary and tags**
  in `index.md`. It never opens the body — so a good `summary` and `tags` matter most.
- **Ask** embeds the whole index into the prompt, then Claude calls `read_file`
  on the articles it needs and answers from their **full body**.

## Writing tips

- **Put the answer in the body, not the summary.** The summary is a pointer; the
  body is the source of truth Ask quotes from.
- **Be exact with numbers.** Prices, limits, and deadlines are quoted verbatim by
  Ask — keep them correct and up to date.
- **Use tables and numbered steps.** They render cleanly and are easy for the
  model to extract.
- **Link related articles** with normal relative markdown links, e.g.
  `[Refunds](../Billing/request-a-refund.md)`. This helps Ask follow context.

## Images

Reference images with Obsidian-style embeds:

```markdown
![[diagram.png]]
```

Put the file in an `_assets/` folder next to the article. The server rewrites the
embed to a short URL and serves the image — no extra setup. (Standard
`![](path)` markdown works too.)

## Categories and the demo

The bundled demo uses these categories: `Getting Started`, `Account`, `Billing`,
`Features`, `Troubleshooting`, `Security`. Delete the demo articles and add your
own — there's nothing special about those names.
