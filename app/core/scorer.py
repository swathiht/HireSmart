"""Scoring engine: TF-IDF + (optional) embeddings + weighted skill overlap, with explanations.

Final match score (0-100) =
    45% weighted skill match   (required skills count more than preferred)
    25% semantic similarity    (embeddings if available, otherwise TF-IDF cosine)
    20% section-weighted keywords (JD terms found in projects/experience count more)
    10% experience / level fit

Every score comes with a plain-English explanation so recruiters and students
can see *why* a number came out the way it did.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

WEIGHTS = {"skills": 0.45, "semantic": 0.25, "keywords": 0.20, "experience": 0.10}
SECTION_WEIGHTS = {"projects": 1.5, "experience": 1.5, "skills": 1.0, "publications": 1.2, "education": 0.6, "other": 0.5}

_STOP_EXTRA = {"experience", "work", "team", "ability", "strong", "good", "skills", "knowledge", "role", "years"}


# --------------------------------------------------------------------------- similarity
def tfidf_similarity(a: str, b: str) -> float:
    if not a.strip() or not b.strip():
        return 0.0
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        m = vec.fit_transform([a, b])
        return float(cosine_similarity(m[0], m[1])[0][0])
    except ValueError:
        return 0.0


@lru_cache(maxsize=1)
def _embedder():
    """Load SentenceTransformer lazily. Enabled with HIRESMART_EMBEDDINGS=1."""
    if os.getenv("HIRESMART_EMBEDDINGS", "0") != "1":
        return None
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(os.getenv("HIRESMART_EMBED_MODEL", "all-MiniLM-L6-v2"))
    except Exception:  # model missing / no internet -> fall back silently
        return None


def semantic_similarity(a: str, b: str) -> tuple[float, str]:
    """Returns (score 0-1, method). Uses embeddings when available."""
    model = _embedder()
    if model is not None:
        emb = model.encode([a[:4000], b[:4000]], normalize_embeddings=True)
        sim = float(emb[0] @ emb[1])
        return max(0.0, min(1.0, sim)), "sentence-embeddings"
    # TF-IDF cosine is typically low in absolute terms; rescale so 0.35 ~ strong match
    raw = tfidf_similarity(a, b)
    return min(1.0, raw / 0.35), "tf-idf"


# --------------------------------------------------------------------------- components
def skill_match(resume_skills: list[str], jd: dict) -> dict:
    have = set(resume_skills)
    req, pref = jd.get("required_skills", []), jd.get("preferred_skills", [])
    weights = jd.get("skill_weights", {})

    def w(s: str, base: float) -> float:
        return base * (1 + 0.25 * min(3, weights.get(s, 1) - 1))

    req_total = sum(w(s, 1.0) for s in req)
    pref_total = sum(w(s, 0.5) for s in pref)
    req_hit = sum(w(s, 1.0) for s in req if s in have)
    pref_hit = sum(w(s, 0.5) for s in pref if s in have)
    total = req_total + pref_total
    score = (req_hit + pref_hit) / total if total else 0.0
    return {
        "score": score,
        "matched_required": [s for s in req if s in have],
        "missing_required": [s for s in req if s not in have],
        "matched_preferred": [s for s in pref if s in have],
        "missing_preferred": [s for s in pref if s not in have],
    }


def _jd_terms(jd: dict) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z+#.\-]{2,}", jd.get("raw_text", "").lower())
    vec_stop = TfidfVectorizer(stop_words="english").get_stop_words()
    return {w for w in words if w not in vec_stop and w not in _STOP_EXTRA}


def section_keyword_score(resume: dict, jd: dict) -> dict:
    """JD terms found in resume sections, weighted by where they were found."""
    terms = _jd_terms(jd) | {s.lower() for s in jd.get("required_skills", []) + jd.get("preferred_skills", [])}
    if not terms:
        return {"score": 0.0, "by_section": {}}
    sec_text = {
        "projects": " ".join(" ".join([p["title"], " ".join(p["tech"]), " ".join(p["bullets"])]) for p in resume["projects"]),
        "experience": " ".join(" ".join([p["title"], " ".join(p["bullets"])]) for p in resume["experience"]),
        "skills": " ".join(resume["skills_listed"]),
        "publications": " ".join(resume["publications"]),
        "education": " ".join(e["text"] for e in resume["education"]),
        "other": " ".join(resume["achievements"]) + " " + resume["summary"],
    }
    credited: dict[str, float] = {}
    by_section: dict[str, float] = {}
    for sec, txt in sec_text.items():
        tokens = set(re.findall(r"[A-Za-z][A-Za-z+#.\-]{2,}", txt.lower()))
        hits = terms & tokens
        by_section[sec] = round(len(hits) / len(terms), 3)
        for t in hits:
            credited[t] = max(credited.get(t, 0.0), SECTION_WEIGHTS[sec])
    max_w = max(SECTION_WEIGHTS.values())
    score = sum(credited.values()) / (len(terms) * max_w)
    # a resume rarely contains every JD word; rescale so ~40% coverage is a strong signal
    return {"score": min(1.0, score / 0.4), "by_section": by_section}


def experience_fit(resume: dict, jd: dict) -> float:
    level = jd.get("level", "entry")
    has_exp = bool(resume["experience"])
    has_projects = len(resume["projects"]) >= 2
    if level == "entry":
        return 1.0 if (has_projects or has_exp) else 0.5
    if level in {"junior", "mid"}:
        return 1.0 if has_exp else (0.6 if has_projects else 0.3)
    return 1.0 if has_exp and len(resume["experience"]) >= 2 else (0.4 if has_exp else 0.2)


# --------------------------------------------------------------------------- main API
def score_resume(resume: dict, jd: dict) -> dict:
    sk = skill_match(resume["skills"], jd)
    sem, sem_method = semantic_similarity(resume["raw_text"], jd.get("raw_text", ""))
    kw = section_keyword_score(resume, jd)
    exp = experience_fit(resume, jd)

    parts = {
        "skills": sk["score"],
        "semantic": sem,
        "keywords": kw["score"],
        "experience": exp,
    }
    overall = sum(parts[k] * WEIGHTS[k] for k in WEIGHTS) * 100
    breakdown = {k: round(v * 100, 1) for k, v in parts.items()}

    return {
        "overall": round(overall, 1),
        "breakdown": breakdown,
        "weights": WEIGHTS,
        "semantic_method": sem_method,
        "skills": sk,
        "keywords_by_section": kw["by_section"],
        "explanation": explain(resume, jd, sk, breakdown, overall),
    }


def explain(resume: dict, jd: dict, sk: dict, breakdown: dict, overall: float) -> str:
    """Plain-English reasons behind the score."""
    lines: list[str] = []
    req_total = len(jd.get("required_skills", []))
    if req_total:
        lines.append(
            f"Matches {len(sk['matched_required'])} of {req_total} required skills"
            + (f" ({', '.join(sk['matched_required'][:6])})" if sk["matched_required"] else "")
            + "."
        )
    if sk["missing_required"]:
        lines.append("Missing required skills: " + ", ".join(sk["missing_required"][:6]) + ".")
    if sk["matched_preferred"]:
        lines.append("Bonus: also has preferred skills " + ", ".join(sk["matched_preferred"][:4]) + ".")

    sec = {k: v for k, v in breakdown.items()}
    strongest = max(sec, key=sec.get)
    weakest = min(sec, key=sec.get)
    label = {"skills": "skill overlap", "semantic": "overall content similarity",
             "keywords": "JD keywords in projects/experience", "experience": "experience level fit"}
    lines.append(f"Strongest area: {label[strongest]} ({sec[strongest]:.0f}/100); weakest: {label[weakest]} ({sec[weakest]:.0f}/100).")

    if resume["projects"]:
        best = max(resume["projects"], key=lambda p: len(set(p["skills"]) & set(jd.get("required_skills", []) + jd.get("preferred_skills", []))))
        shared = set(best["skills"]) & set(jd.get("required_skills", []) + jd.get("preferred_skills", []))
        if shared:
            lines.append(f"Most relevant project: '{best['title']}' (uses {', '.join(sorted(shared)[:4])}).")
    verdict = "Strong match" if overall >= 70 else "Moderate match" if overall >= 45 else "Weak match"
    return f"{verdict}. " + " ".join(lines)
