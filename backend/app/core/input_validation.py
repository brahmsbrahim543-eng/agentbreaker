"""Input validation and sanitization for API endpoints.

Prevents injection attacks, oversized payloads, and malicious input
across the entire ingestion pipeline.
"""

from __future__ import annotations

import html
import re

# ---------------------------------------------------------------------------
# Size limits
# ---------------------------------------------------------------------------
MAX_INPUT_LENGTH = 50_000       # 50 KB max for any single text field
MAX_AGENT_ID_LENGTH = 255       # agent external IDs
MAX_OUTPUT_LENGTH = 100_000     # 100 KB for agent output fields
MAX_STEP_TOKENS = 100_000       # reject steps claiming more than 100K tokens

# Control-character pattern: strip everything except \t (\x09), \n (\x0a), \r (\x0d)
_CTRL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Agent ID: must start with alphanumeric, then alphanumeric / . / - / _
_AGENT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def sanitize_text(text: str | None, max_length: int = MAX_INPUT_LENGTH) -> str:
    """Sanitize free-form text input.

    - Returns empty string for None / empty
    - Truncates to *max_length*
    - Strips null bytes and control characters (keeps \\n, \\t, \\r)
    """
    if not text:
        return ""
    text = text[:max_length]
    text = _CTRL_CHAR_RE.sub("", text)
    return text


def validate_agent_id(agent_id: str) -> str:
    """Validate and return a clean agent ID.

    Raises ``ValueError`` if the ID is empty, too long, or contains
    characters outside the allowed set ``[a-zA-Z0-9._-]``.
    """
    if not agent_id or len(agent_id) > MAX_AGENT_ID_LENGTH:
        raise ValueError(
            f"Agent ID must be between 1 and {MAX_AGENT_ID_LENGTH} characters"
        )
    if not _AGENT_ID_RE.match(agent_id):
        raise ValueError(
            "Agent ID must start with an alphanumeric character and "
            "contain only letters, digits, dots, hyphens, or underscores"
        )
    return agent_id


def sanitize_api_key_name(name: str) -> str:
    """Sanitize an API-key display name to prevent stored XSS."""
    if not name:
        return ""
    return html.escape(name[:100].strip())


def validate_step_tokens(tokens: int) -> int:
    """Reject absurdly large token counts that could skew analytics."""
    if tokens < 0:
        raise ValueError("Token count cannot be negative")
    if tokens > MAX_STEP_TOKENS:
        raise ValueError(
            f"Token count {tokens} exceeds maximum allowed ({MAX_STEP_TOKENS})"
        )
    return tokens
