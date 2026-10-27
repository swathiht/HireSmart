"""Student practice: personalised interview questions and MCQs with instant feedback."""
from __future__ import annotations

from ..core.question_gen import generate_mcqs, generate_questions


def student_questions(resume: dict, jd: dict, n: int = 8, focus: str = "all", difficulty: str | None = None,
                      use_llm: bool = True, seed: int = 0) -> list[dict]:
    return generate_questions(resume, jd, audience="student", n=n, focus=focus, difficulty=difficulty,
                              use_llm=use_llm, seed=seed)


def student_mcqs(resume: dict, jd: dict, n: int = 5, use_llm: bool = True, seed: int = 0) -> list[dict]:
    return generate_mcqs(resume, jd, n=n, use_llm=use_llm, seed=seed)


def check_mcq(mcq: dict, chosen: str) -> dict:
    """Instant feedback for one MCQ answer."""
    correct = chosen == mcq["answer"]
    return {
        "correct": correct,
        "correct_answer": mcq["answer"],
        "feedback": ("Correct! " if correct else f"Not quite. The right answer is: {mcq['answer']}. ") + mcq.get("explanation", ""),
    }


def score_quiz(mcqs: list[dict], answers: dict[int, str]) -> dict:
    """answers maps question index -> chosen option text."""
    results = [check_mcq(m, answers.get(i, "")) | {"skill": m.get("skill", "")} for i, m in enumerate(mcqs) if i in answers]
    correct = sum(r["correct"] for r in results)
    weak = sorted({r["skill"] for r in results if not r["correct"] and r["skill"]})
    return {"answered": len(results), "correct": correct, "total": len(mcqs), "weak_topics": weak, "results": results}
