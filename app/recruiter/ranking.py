"""Recruiter: create jobs, bulk-upload resumes, rank candidates with reasons."""
from __future__ import annotations

from ..core.jd_parser import parse_jd
from ..core.resume_parser import extract_text, parse_resume
from ..core.scorer import score_resume
from ..db import database as db

MAX_FILE_BYTES = 5 * 1024 * 1024
ALLOWED_EXT = (".pdf", ".docx", ".txt")


def create_job(recruiter_id: int, title: str, jd_text: str) -> int:
    if not title.strip() or not jd_text.strip():
        raise ValueError("Job title and description are required.")
    parsed = parse_jd(jd_text)
    return db.save_job(recruiter_id, title.strip(), jd_text, parsed)


def add_resume_files(recruiter_id: int, job_id: int, files: list[tuple[str, bytes]]) -> dict:
    """files = [(filename, bytes)]. Returns {added: [...], errors: [...]}; bad files never stop the batch."""
    job = db.get_job(job_id)
    if not job:
        raise ValueError("Unknown job.")
    added, errors = [], []
    for filename, data in files:
        try:
            if not filename.lower().endswith(ALLOWED_EXT):
                raise ValueError("unsupported file type (use PDF, DOCX or TXT)")
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("file larger than 5 MB")
            parsed = parse_resume(extract_text(data, filename))
            if parsed["word_count"] < 30:
                raise ValueError("could not read enough text (scanned image PDF?)")
            rid = db.save_resume(recruiter_id, parsed, filename, job_id)
            db.save_score(rid, job_id, score_resume(parsed, job))
            added.append({"resume_id": rid, "filename": filename, "name": parsed["name"]})
        except Exception as exc:  # keep processing the rest of the batch
            errors.append({"filename": filename, "error": str(exc)})
    return {"added": added, "errors": errors}


def _display_name(resume: dict, blind: bool, index: int) -> str:
    return f"Candidate {index}" if blind else (resume["name"] or resume["_filename"] or f"Resume {resume['_id']}")


def rank_candidates(job_id: int, min_score: float = 0, required_skills: list[str] | None = None,
                    min_cgpa: float | None = None, keyword: str = "", blind: bool = False) -> list[dict]:
    """Ranked shortlist with match %, matched/missing skills and a plain-English reason."""
    job = db.get_job(job_id)
    if not job:
        raise ValueError("Unknown job.")
    rows = []
    for r in db.list_resumes_for_job(job_id):
        score = db.get_score(r["_id"], job_id) or score_resume(r, job)
        rows.append((r, score))
    rows.sort(key=lambda rs: -rs[1]["overall"])

    out = []
    for r, sc in rows:
        if sc["overall"] < min_score:
            continue
        if required_skills and not set(required_skills) <= set(r["skills"]):
            continue
        if min_cgpa is not None and (r.get("cgpa") or 0) < min_cgpa:
            continue
        if keyword and keyword.lower() not in r["raw_text"].lower():
            continue
        out.append({
            "resume_id": r["_id"],
            "name": _display_name(r, blind, len(out) + 1),
            "match": sc["overall"],
            "breakdown": sc["breakdown"],
            "matched_required": sc["skills"]["matched_required"],
            "missing_required": sc["skills"]["missing_required"],
            "cgpa": None if blind else r.get("cgpa"),
            "reason": sc["explanation"],
        })
    for i, row in enumerate(out, 1):
        row["rank"] = i
        if blind:
            row["name"] = f"Candidate {i}"
    return out


def compare_candidates(job_id: int, resume_ids: list[int]) -> list[dict]:
    """Side-by-side data for 2-3 candidates."""
    job = db.get_job(job_id)
    out = []
    for rid in resume_ids[:3]:
        r = db.get_resume(rid)
        sc = db.get_score(rid, job_id) or score_resume(r, job)
        out.append({"resume_id": rid, "name": r["name"], "match": sc["overall"], "breakdown": sc["breakdown"],
                    "skills": r["skills"], "missing_required": sc["skills"]["missing_required"]})
    return out
