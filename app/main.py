"""FastAPI backend exposing the same services as the Streamlit app.

Run:  uvicorn app.main:app --reload      then open http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .auth.auth import AuthError, create_token, login, register, verify_token
from .core.jd_parser import parse_jd
from .core.resume_parser import extract_text, parse_resume
from .core.scorer import score_resume
from .db import database as db
from .recruiter import interview_kit as kit
from .recruiter.ranking import MAX_FILE_BYTES, add_resume_files, create_job, rank_candidates
from .student.ats import ats_report
from .student.improve import improve_bullets
from .student.practice import student_mcqs, student_questions
from .student.skill_gap import gap_report

app = FastAPI(title="HireSmart API", version="1.0")
db.init_db()


class RegisterIn(BaseModel):
    email: str
    name: str
    password: str = Field(min_length=8)
    role: str


class LoginIn(BaseModel):
    email: str
    password: str


class JobIn(BaseModel):
    title: str
    description: str


def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return verify_token(token)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc


def role_required(role: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] != role:
            raise HTTPException(403, f"Only {role}s can do this.")
        return user
    return dep


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", status_code=201)
def register_user(body: RegisterIn):
    try:
        user = register(body.email, body.name, body.password, body.role)
    except AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"user": user, "token": create_token(user)}


@app.post("/auth/login")
def login_user(body: LoginIn):
    try:
        user = login(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    return {"user": user, "token": create_token(user)}


# --------------------------------------------------------------------------- student
@app.post("/student/analyze")
async def student_analyze(resume: UploadFile = File(...), job_description: str = Form(...),
                          user: dict = Depends(role_required("student"))):
    data = await resume.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File larger than 5 MB.")
    try:
        parsed = parse_resume(extract_text(data, resume.filename))
    except Exception as exc:
        raise HTTPException(422, f"Could not read the resume: {exc}") from exc
    jd = parse_jd(job_description)
    db.save_resume(user["uid"], parsed, resume.filename or "")
    return {
        "score": score_resume(parsed, jd),
        "ats": ats_report(parsed, jd),
        "skill_gap": gap_report(parsed, jd),
        "improvements": improve_bullets(parsed, jd),
        "questions": student_questions(parsed, jd),
        "mcqs": student_mcqs(parsed, jd),
    }


# --------------------------------------------------------------------------- recruiter
@app.post("/recruiter/jobs", status_code=201)
def new_job(body: JobIn, user: dict = Depends(role_required("recruiter"))):
    try:
        return {"job_id": create_job(user["uid"], body.title, body.description)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _own_job(job_id: int, user: dict) -> dict:
    job = db.get_job(job_id)
    if not job or job["_recruiter_id"] != user["uid"]:
        raise HTTPException(404, "Job not found.")
    return job


@app.post("/recruiter/jobs/{job_id}/resumes")
async def upload_resumes(job_id: int, files: list[UploadFile] = File(...), user: dict = Depends(role_required("recruiter"))):
    _own_job(job_id, user)
    payload = [(f.filename or "resume", await f.read()) for f in files]
    return add_resume_files(user["uid"], job_id, payload)


@app.get("/recruiter/jobs/{job_id}/ranking")
def ranking(job_id: int, min_score: float = 0, blind: bool = False, user: dict = Depends(role_required("recruiter"))):
    _own_job(job_id, user)
    return rank_candidates(job_id, min_score=min_score, blind=blind)


@app.post("/recruiter/jobs/{job_id}/candidates/{resume_id}/questions")
def candidate_questions(job_id: int, resume_id: int, n: int = 8, focus: str = "all", user: dict = Depends(role_required("recruiter"))):
    _own_job(job_id, user)
    resume = db.get_resume(resume_id)
    if not resume or resume["_job_id"] != job_id:
        raise HTTPException(404, "Candidate not found for this job.")
    return kit.generate_kit(resume_id, job_id, n=min(max(n, 1), 20), focus=focus)
