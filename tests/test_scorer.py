from app.core.jd_parser import parse_jd
from app.core.resume_parser import parse_resume
from app.core.scorer import score_resume
from pathlib import Path

RES = Path(__file__).parents[1] / "sample_data/resumes"


def _score(name, jd_text):
    return score_resume(parse_resume((RES / name).read_text()), parse_jd(jd_text))


def test_relevant_candidate_beats_irrelevant(jd_text):
    strong = _score("priya_nair.txt", jd_text)["overall"]
    weak = _score("kiran_das.txt", jd_text)["overall"]
    assert strong > weak + 15


def test_scores_are_bounded_and_explained(jd_text):
    for f in RES.glob("*.txt"):
        s = _score(f.name, jd_text)
        assert 0 <= s["overall"] <= 100
        assert all(0 <= v <= 100 for v in s["breakdown"].values())
        assert s["explanation"]


def test_missing_required_skills_are_reported(jd_text):
    s = _score("kiran_das.txt", jd_text)
    assert "FastAPI" in s["skills"]["missing_required"] or "Flask" in s["skills"]["missing_required"]


def test_empty_jd_does_not_crash():
    r = parse_resume((RES / "asha_rao.txt").read_text())
    s = score_resume(r, parse_jd(""))
    assert 0 <= s["overall"] <= 100
