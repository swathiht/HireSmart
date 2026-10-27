"""Job description parser: text -> required / preferred skills, level, role."""
from __future__ import annotations

import re

from .skills import extract_skills, skill_counts

_PREFERRED_MARKERS = re.compile(
    r"(nice to have|good to have|preferred|bonus|plus|desirable|optional|advantage|familiarity with)", re.IGNORECASE
)
_REQUIRED_MARKERS = re.compile(
    r"(required|requirements|must have|must|mandatory|essential|qualifications|you have|what you bring|responsibilities)",
    re.IGNORECASE,
)
_ROLE_RE = re.compile(
    r"([A-Z][A-Za-z/&+\- ]{2,50}?(?:Engineer|Developer|Scientist|Analyst|Intern|Architect|Manager|Researcher|Specialist))"
)


def _split_blocks(text: str) -> list[tuple[str, str]]:
    """Split JD into (context, line) pairs where context is 'required'/'preferred'."""
    context = "required"
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        looks_like_heading = len(s) < 60 and not re.search(r"[.;]$", s)
        if looks_like_heading and _PREFERRED_MARKERS.search(s):
            context = "preferred"
            continue
        if looks_like_heading and _REQUIRED_MARKERS.search(s):
            context = "required"
            continue
        ctx = "preferred" if _PREFERRED_MARKERS.search(s) else context
        out.append((ctx, s))
    return out


def _experience_level(text: str) -> tuple[str, int | None]:
    m = re.search(r"(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)", text, re.IGNORECASE)
    years = int(m.group(1)) if m else None
    low = text.lower()
    if re.search(r"\b(intern|internship|working student|werkstudent|fresher|entry[- ]level|graduate|trainee)\b", low):
        return "entry", years or 0
    if re.search(r"\b(senior|lead|principal|staff)\b", low) or (years and years >= 5):
        return "senior", years
    if years is not None and years >= 2:
        return "mid", years
    return "entry" if years is None else "junior", years


def parse_jd(text: str) -> dict:
    text = text or ""
    blocks = _split_blocks(text)
    required: dict[str, int] = {}
    preferred: dict[str, int] = {}
    for ctx, line in blocks:
        counts = skill_counts(line)
        target = required if ctx == "required" else preferred
        for skill, n in counts.items():
            target[skill] = target.get(skill, 0) + n
    # anything that is both required and preferred stays required
    for s in list(preferred):
        if s in required:
            preferred.pop(s)
    # fallback: no skills found by blocks
    if not required and not preferred:
        for s in extract_skills(text):
            required[s] = 1

    total_mentions = skill_counts(text)
    role_match = _ROLE_RE.search(text)
    level, years = _experience_level(text)
    return {
        "role": role_match.group(1).strip() if role_match else "",
        "level": level,
        "years_required": years,
        "required_skills": sorted(required, key=lambda s: -total_mentions.get(s, 0)),
        "preferred_skills": sorted(preferred, key=lambda s: -total_mentions.get(s, 0)),
        "skill_weights": {s: total_mentions.get(s, 1) for s in {**required, **preferred}},
        "raw_text": text,
    }
