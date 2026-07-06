"""Tool definitions exposed to Claude during Ask mode."""

TOOLS = [
    {
        "name": "read_file",
        "description": (
            "Read one article from the knowledge base. Use the relative path "
            "exactly as it appears in the article index — e.g. "
            "'articles/billing/refunds.md'. Do not prefix paths with the "
            "knowledge-base folder name. The full index is already in your "
            "system prompt, so never call this on the index file itself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Article path relative to the knowledge-base root.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_wiki",
        "description": (
            "Full-text keyword search across every article body. Use this when "
            "the index summaries don't point you to the right article. Returns "
            "a ranked list of matching file paths."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords to search for, e.g. 'refund credit card'.",
                }
            },
            "required": ["query"],
        },
    },
]
