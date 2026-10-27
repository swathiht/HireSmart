"""SQLite storage. Swap `connect()` for a PostgreSQL connection later if you want."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "hiresmart.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'recruiter')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    job_id INTEGER REFERENCES jobs(id),
    filename TEXT,
    candidate_name TEXT,
    parsed_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    parsed_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL REFERENCES resumes(id),
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    overall REAL NOT NULL,
    breakdown_json TEXT NOT NULL,
    explanation TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (resume_id, job_id)
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL REFERENCES resumes(id),
    job_id INTEGER REFERENCES jobs(id),
    kind TEXT NOT NULL DEFAULT 'question',     -- 'question' or 'mcq'
    category TEXT,
    difficulty TEXT,
    payload_json TEXT NOT NULL,                -- question, why, rubric, follow_up ... / options, answer ...
    is_custom INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def db_path() -> str:
    return os.getenv("HIRESMART_DB", str(DEFAULT_DB))


@contextmanager
def connect():
    path = db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# --------------------------------------------------------------------------- resumes
def save_resume(user_id: int, parsed: dict, filename: str = "", job_id: int | None = None) -> int:
    slim = {k: v for k, v in parsed.items()}
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO resumes (user_id, job_id, filename, candidate_name, parsed_json) VALUES (?,?,?,?,?)",
            (user_id, job_id, filename, parsed.get("name", ""), json.dumps(slim)),
        )
        return cur.lastrowid


def get_resume(resume_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM resumes WHERE id=?", (resume_id,)).fetchone()
    if not row:
        return None
    data = json.loads(row["parsed_json"])
    data["_id"] = row["id"]
    data["_filename"] = row["filename"]
    data["_user_id"] = row["user_id"]
    data["_job_id"] = row["job_id"]
    return data


def latest_resume_for_user(user_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM resumes WHERE user_id=? AND job_id IS NULL ORDER BY id DESC LIMIT 1", (user_id,)
        ).fetchone()
    return get_resume(row["id"]) if row else None


def list_resumes_for_job(job_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT id FROM resumes WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
    return [get_resume(r["id"]) for r in rows]


# --------------------------------------------------------------------------- jobs
def save_job(recruiter_id: int, title: str, jd_text: str, parsed: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (recruiter_id, title, jd_text, parsed_json) VALUES (?,?,?,?)",
            (recruiter_id, title, jd_text, json.dumps(parsed)),
        )
        return cur.lastrowid


def get_job(job_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    data = json.loads(row["parsed_json"])
    data.update({"_id": row["id"], "title": row["title"], "_recruiter_id": row["recruiter_id"]})
    return data


def list_jobs(recruiter_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM jobs WHERE recruiter_id=? ORDER BY id DESC", (recruiter_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- scores
def save_score(resume_id: int, job_id: int, score: dict) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO scores (resume_id, job_id, overall, breakdown_json, explanation)
               VALUES (?,?,?,?,?)
               ON CONFLICT(resume_id, job_id) DO UPDATE SET
                 overall=excluded.overall, breakdown_json=excluded.breakdown_json, explanation=excluded.explanation""",
            (resume_id, job_id, score["overall"], json.dumps(score), score.get("explanation", "")),
        )


def get_score(resume_id: int, job_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT breakdown_json FROM scores WHERE resume_id=? AND job_id=?", (resume_id, job_id)).fetchone()
    return json.loads(row["breakdown_json"]) if row else None


# --------------------------------------------------------------------------- questions
def replace_questions(resume_id: int, job_id: int | None, items: list[dict], kind: str = "question") -> None:
    """Replace generated (non-custom) items of this kind; keep recruiter-added custom ones."""
    with connect() as conn:
        conn.execute(
            "DELETE FROM questions WHERE resume_id=? AND job_id IS ? AND kind=? AND is_custom=0",
            (resume_id, job_id, kind),
        )
        for it in items:
            conn.execute(
                "INSERT INTO questions (resume_id, job_id, kind, category, difficulty, payload_json) VALUES (?,?,?,?,?,?)",
                (resume_id, job_id, kind, it.get("category"), it.get("difficulty"), json.dumps(it)),
            )


def add_custom_question(resume_id: int, job_id: int | None, item: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO questions (resume_id, job_id, kind, category, difficulty, payload_json, is_custom) VALUES (?,?,?,?,?,?,1)",
            (resume_id, job_id, "question", item.get("category", "custom"), item.get("difficulty", "medium"), json.dumps(item)),
        )
        return cur.lastrowid


def load_questions(resume_id: int, job_id: int | None, kind: str = "question") -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, payload_json, is_custom FROM questions WHERE resume_id=? AND job_id IS ? AND kind=? ORDER BY id",
            (resume_id, job_id, kind),
        ).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["payload_json"])
        d["_id"], d["is_custom"] = r["id"], bool(r["is_custom"])
        out.append(d)
    return out


def delete_question(question_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM questions WHERE id=?", (question_id,))
