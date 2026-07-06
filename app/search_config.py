"""
Language & domain tuning for the built-in keyword search engine.

This is the ONE file you edit to adapt the search engine to your own content
and language. Everything here ships with sensible English defaults plus a few
demo-specific entries. Replace them with terms that match your knowledge base.

None of this requires an LLM — "Search" mode is pure server-side scoring.

See docs/SEARCH_TUNING.md for a walkthrough.
"""

# ---------------------------------------------------------------------------
# STOP_WORDS — removed from queries before scoring. They add noise, not signal.
# These are common English function words. Swap for your language as needed.
# ---------------------------------------------------------------------------
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "is", "are", "was",
    "were", "be", "been", "being", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "that", "this", "these", "those", "it", "its",
    "i", "you", "he", "she", "we", "they", "my", "your", "our", "their",
    "do", "does", "did", "how", "what", "when", "where", "why", "which",
    "who", "can", "could", "should", "would", "will", "about", "into",
    "over", "under", "again", "not", "no", "yes", "please", "help", "info",
    "information", "guide", "article", "articles", "find", "show", "tell",
}

# ---------------------------------------------------------------------------
# TECH_TERMS — short tokens (under 4 chars) that should NOT be discarded.
# Acronyms, product codes, error codes, etc. Add your own.
# ---------------------------------------------------------------------------
TECH_TERMS = frozenset({
    "api", "sso", "2fa", "mfa", "url", "pdf", "csv", "vpn", "dns", "ios",
})

# ---------------------------------------------------------------------------
# SYNONYMS — query-expansion map. A matched key also searches its values.
# Bidirectional links are not automatic — add both directions if you want them.
# ---------------------------------------------------------------------------
SYNONYMS = {
    "login": ["signin", "sign-in", "log-in", "authenticate"],
    "signin": ["login"],
    "password": ["passcode", "credentials"],
    "cancel": ["cancellation", "terminate", "unsubscribe"],
    "refund": ["reimburse", "credit", "chargeback"],
    "invoice": ["bill", "receipt", "billing"],
    "plan": ["subscription", "tier", "package"],
    "cost": ["price", "pricing"],
    "price": ["pricing", "cost"],
    "delete": ["remove", "erase"],
}

# ---------------------------------------------------------------------------
# CATEGORY_BOOST — keyword -> category path fragment(s). When a query keyword
# matches, articles whose path contains the fragment get a relevance boost.
# Use this to steer ambiguous queries toward the right section.
# Fragments are matched case-insensitively against the article path.
# ---------------------------------------------------------------------------
CATEGORY_BOOST = {
    "billing": ["Billing"],
    "invoice": ["Billing"],
    "payment": ["Billing"],
    "refund": ["Billing"],
    "plan": ["Billing"],
    "cost": ["Billing"],
    "price": ["Billing"],
    "login": ["Account"],
    "password": ["Account"],
    "account": ["Account"],
    "profile": ["Account"],
    "error": ["Troubleshooting"],
    "sync": ["Troubleshooting"],
    "crash": ["Troubleshooting"],
    "upload": ["Features"],
    "share": ["Features"],
    "security": ["Security"],
    "privacy": ["Security"],
}

# ---------------------------------------------------------------------------
# KNOWN_PHRASES — multi-word phrases (lowercase) that should score extra when
# they appear verbatim in both the query and an article title.
# ---------------------------------------------------------------------------
KNOWN_PHRASES = frozenset({
    "two factor", "two-factor", "2fa", "single sign-on", "sign in",
    "forgot password", "free trial", "payment method", "file upload",
})

# ---------------------------------------------------------------------------
# SUFFIXES — light stemmer. Stripped from query words (longest match first) so
# "uploading" also matches "upload". Empty the tuple to disable stemming.
# Order matters: list longer suffixes first.
# ---------------------------------------------------------------------------
SUFFIXES = (
    "ization", "izations", "ements", "ement", "ations", "ation",
    "ingly", "fully", "ings", "ing", "edly", "ies", "ied",
    "ness", "ment", "able", "ible", "ers", "er", "ed", "es", "s",
)

# Minimum length of the remaining stem before a suffix may be stripped.
MIN_STEM = 4
