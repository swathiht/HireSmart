import pytest

from app.auth.auth import register
from app.db import database as db
from app.recruiter import interview_kit as kit
from app.recruiter.ranking import add_resume_files, compare_candidates, create_job, rank_candidates
from app.reports.pdf import interview_kit_pdf


@pytest.fixture
def setup(jd_text, sample_files):
    rec = register("rec@example.com", "Rec", "password123", "recruiter")
    job_id = create_job(rec["id"], "AI/ML Working Student", jd_text)
    result = add_resume_files(rec["id"], job_id, sample_files)
    return rec, job_id, result


def test_bulk_upload_and_ranking(setup):
    rec, job_id, result = setup
    assert len(result["added"]) == 5 and not result["errors"]
    ranked = rank_candidates(job_id)
    assert [r["rank"] for r in ranked] == [1, 2, 3, 4, 5]
    scores = [r["match"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0]["reason"]
    names = [r["name"] for r in ranked]
    assert names.index("Priya Nair") < names.index("Kiran Das")


def test_bad_files_do_not_stop_the_batch(jd_text):
    rec = register("r2@example.com", "R", "password123", "recruiter")
    job_id = create_job(rec["id"], "Role", jd_text)
    res = add_resume_files(rec["id"], job_id, [
        ("notes.exe", b"x"), ("empty.txt", b"too short"), ("big.txt", b"a" * (6 * 1024 * 1024)),
        ("ok.txt", b"Jane Roe\njane@example.com\nSkills\nPython, SQL, Docker, Git, FastAPI, NLP\nProjects\nApp | Python\n" + b"- Built an app using python and sql with many words " * 8),
    ])
    assert len(res["added"]) == 1 and len(res["errors"]) == 3


def test_filters_and_blind_screening(setup):
    _, job_id, _ = setup
    assert all("Python" in db.get_resume(r["resume_id"])["skills"] for r in rank_candidates(job_id, required_skills=["Python"]))
    assert all((r["cgpa"] or 0) >= 8.5 for r in rank_candidates(job_id, min_cgpa=8.5))
    assert all(r["match"] >= 50 for r in rank_candidates(job_id, min_score=50))
    blind = rank_candidates(job_id, blind=True)
    assert all(r["name"].startswith("Candidate ") and r["cgpa"] is None for r in blind)
    assert not any("Priya" in r["name"] for r in blind)


def test_candidate_page_and_interview_kit(setup):
    _, job_id, _ = setup
    top = rank_candidates(job_id)[0]["resume_id"]
    view = kit.candidate_view(top, job_id)
    assert view["strengths"] and view["resume"]["projects"] and view["questions"] == []

    qs = kit.generate_kit(top, job_id, n=8, use_llm=False)
    assert len(qs) == 8 and {q["category"] for q in qs} >= {"project", "technical"}
    assert all(q["why"] and len(q["rubric"]) == 3 and q["follow_up"] for q in qs)
    assert kit.candidate_view(top, job_id)["questions"], "questions are saved for the candidate"

    # custom question survives regeneration; removing works
    qs = kit.add_custom(top, job_id, "Tell me about your IEEE paper review process.", "hr")
    custom_id = [q for q in qs if q["is_custom"]][0]["_id"]
    regenerated = kit.generate_kit(top, job_id, n=6, focus="technical", use_llm=False)
    assert any(q["is_custom"] for q in regenerated) and len([q for q in regenerated if not q["is_custom"]]) == 6
    kit.remove_question(custom_id)
    assert not any(q["is_custom"] for q in kit.candidate_view(top, job_id)["questions"])

    view = kit.candidate_view(top, job_id)
    pdf = interview_kit_pdf(view["resume"]["name"], view["job"]["title"], view["score"], view["strengths"], view["gaps"], view["questions"])
    assert pdf[:4] == b"%PDF"


def test_gap_and_verification_questions_are_grounded(setup):
    _, job_id, _ = setup
    kiran = [r for r in rank_candidates(job_id) if r["name"] == "Kiran Das"][0]["resume_id"]
    qs = kit.generate_kit(kiran, job_id, n=10, use_llm=False)
    gaps = [q for q in qs if q["category"] == "gap"]
    assert gaps and all("requires" in q["question"] for q in gaps)
    asha = [r for r in rank_candidates(job_id) if r["name"] == "Asha Rao"][0]["resume_id"]
    ver = [q for q in kit.generate_kit(asha, job_id, n=10, use_llm=False) if q["category"] == "verification"]
    assert ver and any("91.2%" in q["question"] or "88%" in q["question"] or "35%" in q["question"] for q in ver)


def test_compare_candidates(setup):
    _, job_id, _ = setup
    ids = [r["resume_id"] for r in rank_candidates(job_id)[:3]]
    cmp = compare_candidates(job_id, ids)
    assert len(cmp) == 3 and all("breakdown" in c for c in cmp)
