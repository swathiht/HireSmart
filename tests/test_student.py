from pathlib import Path

from app.core.jd_parser import parse_jd
from app.core.resume_parser import parse_resume
from app.core.scorer import score_resume
from app.reports.pdf import student_report_pdf
from app.student.ats import ats_report
from app.student.improve import improve_bullets
from app.student.practice import score_quiz, student_mcqs, student_questions
from app.student.skill_gap import gap_report

RES = Path(__file__).parents[1] / "sample_data/resumes"


def _setup(name, jd_text):
    return parse_resume((RES / name).read_text()), parse_jd(jd_text)


def test_ats_sections_add_up(jd_text):
    r, jd = _setup("asha_rao.txt", jd_text)
    ats = ats_report(r, jd)
    assert sum(s["max"] for s in ats["sections"]) == 100
    assert abs(sum(s["score"] for s in ats["sections"]) - ats["overall"]) < 0.2
    assert 0 <= ats["overall"] <= 100


def test_ats_better_resume_scores_higher(jd_text):
    good = ats_report(*_setup("asha_rao.txt", jd_text))["overall"]
    weak = ats_report(*_setup("rohan_mehta.txt", jd_text))["overall"]
    assert good > weak


def test_gap_report_ranks_required_first(jd_text):
    r, jd = _setup("kiran_das.txt", jd_text)
    g = gap_report(r, jd)
    assert g["gaps"], "a data-analyst resume should have gaps for an ML role"
    imp = [x["importance"] for x in g["gaps"]]
    assert imp == sorted(imp, reverse=True)
    assert all(x["what_to_learn"] and x["mini_project"] for x in g["gaps"])
    assert g["gaps"][0]["type"] == "required"


def test_improve_rewrites_weak_bullets(jd_text):
    r, jd = _setup("rohan_mehta.txt", jd_text)
    items = improve_bullets(r, jd, use_llm=False)
    weak = [i for i in items if i["original"].startswith("Worked on")][0]
    assert weak["suggestion"].startswith("Built")
    assert "[add result" in weak["suggestion"]        # placeholder, never an invented number


def test_questions_have_full_structure(jd_text):
    r, jd = _setup("asha_rao.txt", jd_text)
    qs = student_questions(r, jd, n=8)
    assert len(qs) == 8
    for q in qs:
        assert q["question"] and q["why"] and q["follow_up"] and len(q["rubric"]) == 3
        assert q["difficulty"] in {"easy", "medium", "hard"}


def test_mcq_instant_feedback(jd_text):
    r, jd = _setup("asha_rao.txt", jd_text)
    mcqs = student_mcqs(r, jd, n=5)
    assert len(mcqs) == 5
    for m in mcqs:
        assert m["answer"] in m["options"] and len(set(m["options"])) == 4 and m["explanation"]
    answers = {0: mcqs[0]["answer"], 1: "definitely wrong option"}
    res = score_quiz(mcqs, answers)
    assert res["correct"] == 1 and res["answered"] == 2
    assert res["results"][1]["feedback"].startswith("Not quite")


def test_student_pdf_report_builds(jd_text):
    r, jd = _setup("asha_rao.txt", jd_text)
    pdf = student_report_pdf(r, jd, score_resume(r, jd), ats_report(r, jd), gap_report(r, jd),
                             improve_bullets(r, jd, use_llm=False), student_questions(r, jd), student_mcqs(r, jd))
    assert pdf[:4] == b"%PDF" and len(pdf) > 3000
