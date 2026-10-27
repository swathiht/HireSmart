from pathlib import Path

from fastapi.testclient import TestClient

SAMPLES = Path(__file__).parents[1] / "sample_data"


def _client():
    from app.main import app
    return TestClient(app)


def _signup(c, role, email):
    r = c.post("/auth/register", json={"email": email, "name": "T", "password": "password123", "role": role})
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_health_and_auth_errors():
    c = _client()
    assert c.get("/health").json() == {"status": "ok"}
    assert c.post("/auth/login", json={"email": "no@example.com", "password": "password123"}).status_code == 401
    assert c.post("/student/analyze", data={"job_description": "x"}).status_code in (401, 422)


def test_role_enforcement():
    c = _client()
    stu = _signup(c, "student", "s@example.com")
    rec = _signup(c, "recruiter", "r@example.com")
    assert c.post("/recruiter/jobs", json={"title": "T", "description": "Python"}, headers=stu).status_code == 403
    resume = (SAMPLES / "resumes" / "asha_rao.txt").read_bytes()
    r = c.post("/student/analyze", files={"resume": ("a.txt", resume)}, data={"job_description": (SAMPLES / "job_description.txt").read_text()}, headers=rec)
    assert r.status_code == 403


def test_student_and_recruiter_endpoints():
    c = _client()
    stu = _signup(c, "student", "s@example.com")
    jd = (SAMPLES / "job_description.txt").read_text()
    r = c.post("/student/analyze", files={"resume": ("a.txt", (SAMPLES / "resumes" / "asha_rao.txt").read_bytes())}, data={"job_description": jd}, headers=stu)
    assert r.status_code == 200
    body = r.json()
    assert {"score", "ats", "skill_gap", "improvements", "questions", "mcqs"} <= set(body)

    rec = _signup(c, "recruiter", "r@example.com")
    job = c.post("/recruiter/jobs", json={"title": "ML", "description": jd}, headers=rec).json()["job_id"]
    files = [("files", (p.name, p.read_bytes())) for p in (SAMPLES / "resumes").glob("*.txt")]
    up = c.post(f"/recruiter/jobs/{job}/resumes", files=files, headers=rec).json()
    assert len(up["added"]) == 5
    ranking = c.get(f"/recruiter/jobs/{job}/ranking", headers=rec).json()
    assert ranking[0]["rank"] == 1
    qs = c.post(f"/recruiter/jobs/{job}/candidates/{ranking[0]['resume_id']}/questions", headers=rec).json()
    assert len(qs) == 8

    # another recruiter cannot see this job
    other = _signup(c, "recruiter", "r2@example.com")
    assert c.get(f"/recruiter/jobs/{job}/ranking", headers=other).status_code == 404
