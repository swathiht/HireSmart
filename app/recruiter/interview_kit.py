"""Candidate page data + interview kit (generate, save, edit, add custom questions, export)."""
from __future__ import annotations

from ..core.question_gen import CATEGORY_LABELS, generate_questions
from ..core.scorer import score_resume
from ..db import database as db


def candidate_view(resume_id: int, job_id: int) -> dict:
    """Everything the candidate page shows: resume, score, strengths/gaps and saved questions."""
    resume, job = db.get_resume(resume_id), db.get_job(job_id)
    if not resume or not job:
        raise ValueError("Unknown candidate or job.")
    score = db.get_score(resume_id, job_id) or score_resume(resume, job)
    sk = score["skills"]
    return {
        "resume": resume, "job": job, "score": score,
        "strengths": sk["matched_required"] + sk["matched_preferred"],
        "gaps": sk["missing_required"],
        "questions": db.load_questions(resume_id, job_id),
    }


def generate_kit(resume_id: int, job_id: int, n: int = 8, focus: str = "all", difficulty: str | None = None,
                 use_llm: bool = True, seed: int = 0) -> list[dict]:
    """Generate questions for a candidate, keep any custom questions, and save the result."""
    resume, job = db.get_resume(resume_id), db.get_job(job_id)
    if not resume or not job:
        raise ValueError("Unknown candidate or job.")
    items = generate_questions(resume, job, audience="recruiter", n=n, focus=focus, difficulty=difficulty,
                               use_llm=use_llm, seed=seed)
    db.replace_questions(resume_id, job_id, items)
    return db.load_questions(resume_id, job_id)


def add_custom(resume_id: int, job_id: int, question: str, category: str = "technical",
               difficulty: str = "medium", rubric: list[str] | None = None) -> list[dict]:
    if not question.strip():
        raise ValueError("Question text is required.")
    cat = category if category in CATEGORY_LABELS else "technical"
    db.add_custom_question(resume_id, job_id, {
        "question": question.strip(), "category": cat, "category_label": CATEGORY_LABELS[cat], "difficulty": difficulty,
        "why": "Added by the recruiter.", "evidence": "", "rubric": rubric or [], "follow_up": "",
    })
    return db.load_questions(resume_id, job_id)


def remove_question(question_id: int) -> None:
    db.delete_question(question_id)
