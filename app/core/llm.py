"""Optional LLM access.

If ANTHROPIC_API_KEY is set (and the `anthropic` package is installed) the
question / MCQ / rewrite generators use the LLM. Otherwise every feature falls
back to the built-in rule-based generators, so the whole app runs for free.
"""
from __future__ import annotations

import json
import os
import re

DEFAULT_MODEL = os.getenv("HIRESMART_LLM_MODEL", "claude-sonnet-5-5")


def llm_available() -> bool:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def llm_text(prompt: str, system: str = "", max_tokens: int = 3000) -> str:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=system or "You are a precise assistant. Follow the requested output format exactly.",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = min([i for i in (text.find("["), text.find("{")) if i != -1], default=-1)
    if start > 0:
        text = text[start:]
    return json.loads(text)


def llm_json(prompt: str, system: str = "", retries: int = 1):
    """Call the LLM and parse JSON. Retries once if the output is malformed; returns None on failure."""
    for _ in range(retries + 1):
        try:
            return _extract_json(llm_text(prompt, system))
        except Exception:
            continue
    return None
