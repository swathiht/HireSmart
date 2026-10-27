"""Resume improvement suggestions: find weak bullets and rewrite them in action + result format."""
from __future__ import annotations

import json
import re

from ..core.llm import llm_available, llm_json
from .ats import ACTION_VERBS, _first_word

WEAK_STARTS = [
    (r"^(?:was |were )?responsible for\s+", "Owned "),
    (r"^worked on\s+", "Built "),
    (r"^worked with\s+", "Applied "),
    (r"^helped (?:to )?\s*", "Contributed to "),
    (r"^involved in\s+", "Contributed to "),
    (r"^made\s+", "Developed "),
    (r"^did\s+", "Completed "),
    (r"^used\s+", "Applied "),
    (r"^tasked with\s+", "Delivered "),
    (r"^participated in\s+", "Took part in "),
]
_NUM_RE = re.compile(r"\d")


def _issues(bullet: str) -> list[str]:
    out = []
    words = bullet.split()
    if _first_word(bullet) not in ACTION_VERBS:
        out.append("Does not start with a strong action verb")
    if not _NUM_RE.search(bullet):
        out.append("No measurable result (number, %, size, time)")
    if len(words) < 8:
        out.append("Too short: say what you did, how, and the result")
    if len(words) > 32:
        out.append("Too long: split it or trim to one idea")
    return out


def _rule_rewrite(bullet: str, jd_missing: list[str]) -> str:
    text = bullet.strip().rstrip(".")
    for pat, repl in WEAK_STARTS:
        if re.match(pat, text, re.IGNORECASE):
            text = repl + re.sub(pat, "", text, flags=re.IGNORECASE)
            break
    else:
        if _first_word(text) not in ACTION_VERBS:
            text = "Developed " + text[0].lower() + text[1:] if text else text
    if not _NUM_RE.search(text):
        text += ", achieving [add result: accuracy %, time saved, users or data size]"
    return text + "."


def improve_bullets(resume: dict, jd: dict | None = None, max_items: int = 8, use_llm: bool = True) -> list[dict]:
    """Return [{original, issues, suggestion, source}] for the weakest bullets."""
    jd = jd or {}
    missing = [s for s in jd.get("required_skills", []) if s not in set(resume["skills"])]
    candidates = []
    for b in resume["bullets"]:
        issues = _issues(b)
        if issues:
            candidates.append((len(issues), b, issues))
    candidates.sort(key=lambda x: -x[0])
    chosen = candidates[:max_items]
    results = [{"original": b, "issues": iss, "suggestion": _rule_rewrite(b, missing), "source": "rules"} for _, b, iss in chosen]

    if use_llm and llm_available() and results:
        prompt = f"""Rewrite each resume bullet in "action verb + what + how + measurable result" format (max 25 words).
Do NOT invent facts or numbers. If a number is unknown, use a placeholder like [X%].
Target role skills (only mention if already implied): {', '.join(jd.get('required_skills', [])[:8])}
Return ONLY a JSON list of strings, in the same order, one rewrite per bullet.
BULLETS: {json.dumps([r['original'] for r in results])}"""
        data = llm_json(prompt)
        if isinstance(data, list) and len(data) == len(results) and all(isinstance(x, str) for x in data):
            for r, new in zip(results, data):
                r["suggestion"], r["source"] = new, "llm"
    return results
