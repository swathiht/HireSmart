"""ATS score (0-100) with a section-wise breakdown and concrete tips."""
from __future__ import annotations

import re

from ..core.scorer import skill_match

ACTION_VERBS = {
    "built", "developed", "designed", "implemented", "created", "engineered", "deployed", "optimised", "optimized",
    "automated", "analysed", "analyzed", "trained", "evaluated", "integrated", "led", "managed", "organised", "organized",
    "co-organised", "co-organized", "published", "reduced", "improved", "increased", "achieved", "architected", "migrated",
    "refactored", "applied", "collaborated", "coordinated", "launched", "streamlined", "extracted", "generated", "produced",
}
_NUMBER_RE = re.compile(r"\d")


def _first_word(bullet: str) -> str:
    m = re.match(r"[A-Za-z\-]+", bullet.strip())
    return m.group(0).lower() if m else ""


def ats_report(resume: dict, jd: dict) -> dict:
    """Return {overall, sections:[{name, score, max, tips}], summary}."""
    sections: list[dict] = []

    # 1. Keyword match (40)
    sk = skill_match(resume["skills"], jd)
    kw_score = sk["score"] * 40
    tips = []
    if sk["missing_required"]:
        tips.append("Add (only if true) these required skills: " + ", ".join(sk["missing_required"][:6]) + ".")
    if not tips:
        tips.append("Great keyword coverage for this job description.")
    sections.append({"name": "Keyword match", "score": round(kw_score, 1), "max": 40, "tips": tips})

    # 2. Section completeness (20)
    expected = {"education": 4, "skills": 4, "projects": 5, "experience": 3, "summary": 2, "achievements": 2}
    found = set(resume["sections_found"])
    comp = sum(pts for sec, pts in expected.items() if sec in found)
    # experience is not expected from freshers: give credit if projects are strong
    if "experience" not in found and len(resume["projects"]) >= 2:
        comp += 3
    tips = []
    for sec, label in [("summary", "a 2-line summary/objective"), ("experience", "an Experience / Internship section"),
                       ("projects", "a Projects section"), ("skills", "a Skills section"), ("education", "an Education section")]:
        if sec not in found and not (sec == "experience" and len(resume["projects"]) >= 2):
            tips.append(f"Add {label}.")
    sections.append({"name": "Section completeness", "score": float(min(20, comp)), "max": 20,
                     "tips": tips or ["All key sections are present."]})

    # 3. Contact & format (10)
    pts, tips = 0.0, []
    for ok, p, tip in [
        (bool(resume["email"]), 3, "Add a professional email address."),
        (bool(resume["phone"]), 2, "Add a phone number."),
        (bool(resume["links"]), 3, "Add GitHub / LinkedIn links."),
        (200 <= resume["word_count"] <= 900, 2, "Aim for roughly 250-800 words (one page for freshers)."),
    ]:
        pts += p if ok else 0
        if not ok:
            tips.append(tip)
    sections.append({"name": "Contact & format", "score": pts, "max": 10, "tips": tips or ["Contact details and length look good."]})

    # 4. Quantified impact (15)
    bullets = resume["bullets"]
    with_numbers = [b for b in bullets if _NUMBER_RE.search(b)]
    ratio = len(with_numbers) / len(bullets) if bullets else 0.0
    sections.append({
        "name": "Quantified impact", "score": round(min(1.0, ratio / 0.5) * 15, 1), "max": 15,
        "tips": ["Add numbers (accuracy, users, time saved, dataset size) to more bullets."] if ratio < 0.5
        else ["Good use of measurable results."],
    })

    # 5. Action verbs (15)
    strong = [b for b in bullets if _first_word(b) in ACTION_VERBS]
    ratio_v = len(strong) / len(bullets) if bullets else 0.0
    weak_examples = [b for b in bullets if _first_word(b) not in ACTION_VERBS][:2]
    tips = [f"Start with a strong verb: \"{w[:60]}...\"" for w in weak_examples] or ["Bullets start with strong action verbs."]
    sections.append({"name": "Action verbs", "score": round(ratio_v * 15, 1), "max": 15, "tips": tips})

    overall = round(sum(s["score"] for s in sections), 1)
    weakest = min(sections, key=lambda s: s["score"] / s["max"])
    summary = (f"ATS score {overall}/100. " +
               ("Excellent." if overall >= 80 else "Good, with room to improve." if overall >= 60 else "Needs work.") +
               f" Biggest opportunity: {weakest['name'].lower()}.")
    return {"overall": overall, "sections": sections, "summary": summary,
            "matched_required": sk["matched_required"], "missing_required": sk["missing_required"]}
