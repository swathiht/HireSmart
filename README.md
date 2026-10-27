# 🎯 HireSmart: Two-Sided AI Hiring Platform

HireSmart has one shared NLP engine and two workspaces.

- **Students** upload a resume and a job description. They get an ATS score, a skill-gap analysis, resume-bullet rewrites, personalised interview questions, MCQ practice with instant feedback, and a PDF report.
- **Recruiters** add a job and bulk-upload resumes. They get a ranked shortlist with a reason for each rank, a candidate page (resume next to generated interview questions), and an interview kit they can export as PDF.

It runs **offline and free**. Without an API key, questions come from a built-in generator. With `ANTHROPIC_API_KEY` set, the LLM generates questions, MCQs and bullet rewrites, and the built-in generator stays as the fallback.

## Features

| Shared core | Student | Recruiter |
|---|---|---|
| Resume parser (PDF/DOCX/TXT) | ATS score with 5 sections | Job + JD parsing (required vs preferred skills) |
| JD parser | Skill gap with learning plan | Bulk resume upload (bad files don't stop the batch) |
| 80+ skills with aliases | Resume bullet rewrites | Ranked shortlist with match % and reasons |
| TF-IDF + embeddings + section-weighted scoring | Personalised questions | Candidate page: resume on the left, questions on the right |
| Score explanations | MCQs with feedback | Question types: project, technical, gap, verification, HR |
| Role-based login | PDF report | Each question has difficulty, why, evidence, rubric and follow-up |
| SQLite storage | | Custom questions, filters, blind screening, compare view, CSV and PDF export |

*Not included (by design): voice mock interview, attempt history, cloud deployment.*

## Architecture

```
            ┌───────────── Streamlit UI (frontend/streamlit_app.py) ─────────────┐
            │   Student workspace                    Recruiter workspace         │
            └──────────┬─────────────────────────────────────┬──────────────────┘
                       │            (or REST: app/main.py)    │
        app/student/ ──┤                                      ├── app/recruiter/
        ats · skill_gap│                                      │   ranking · interview_kit
        improve · practice                                    │
                       └──────────────┬───────────────────────┘
                                      ▼
                     app/core/   skills · resume_parser · jd_parser
                                 scorer · question_gen · llm
                                      │
                     app/auth/  app/db/ (SQLite)  app/reports/ (PDF)
```

### How a match score is computed (0–100)

| Component | Weight | What it measures |
|---|---|---|
| Skill match | 45% | Required skills count more than preferred ones; skills the JD repeats count more |
| Semantic similarity | 25% | Embeddings if enabled, otherwise TF-IDF cosine similarity |
| Section-weighted keywords | 20% | JD terms found in projects/experience count more than terms in the skills list or education |
| Experience fit | 10% | Does the candidate's background fit the job level? |

Every score comes with a plain-English explanation, so recruiters and students can see why it came out as it did.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run frontend/streamlit_app.py               # the app
uvicorn app.main:app --reload                         # optional REST API, docs at /docs
pytest -q                                             # 36 tests
```

1. Create an account and choose **student** or **recruiter**.
2. Use the **sample resume**, **sample job description** and **5 sample resumes** buttons to try everything without your own files.

### Optional upgrades

```bash
pip install sentence-transformers && export HIRESMART_EMBEDDINGS=1   # semantic embeddings
pip install anthropic && export ANTHROPIC_API_KEY=sk-...             # LLM questions / MCQs / rewrites
```

## Project structure

```
hiresmart/
├── app/
│   ├── main.py              FastAPI (JWT-style tokens, role-protected routes)
│   ├── auth/auth.py         register / login / roles (PBKDF2 hashes)
│   ├── core/                skills · resume_parser · jd_parser · scorer · question_gen · llm
│   ├── student/             ats · skill_gap · improve · practice
│   ├── recruiter/           ranking · interview_kit
│   ├── reports/pdf.py       student report + interview kit (ReportLab)
│   └── db/database.py       SQLite: users, resumes, jobs, scores, questions
├── frontend/streamlit_app.py
├── sample_data/             5 fake resumes + a sample job description
├── tests/                   36 tests (parser, scorer, auth, student, recruiter, API, UI)
├── requirements.txt
└── README.md
```

## Design decisions

- **Grounded questions.** Every generated question carries the resume evidence it came from. The prompt for the LLM engine says to use only facts in the resume or job, and the fallback engine is template-based on parsed data.
- **No invented numbers.** Resume rewrites use placeholders such as `[add result: …]`. They never make up metrics.
- **Failure isolation.** A corrupt or oversized file is reported and skipped, and the rest of the batch continues.
- **Explainability.** A ranking comes with reasons, not just a number. Blind screening hides names, contact details and CGPA.
- **Privacy.** Passwords are salted PBKDF2 hashes. Use fake or sample resumes in any shared demo.

## Limitations (be honest about these in interviews)

- Parsing is rule-based and tuned for common resume layouts. Unusual two-column designs may parse imperfectly, and scanned image PDFs are rejected.
- The skill dictionary is hand-written (80+ skills). Unknown skills are not detected until added to `app/core/skills.py`.
- Scores are heuristics. They have not been validated against human hiring decisions. A good next step is to rank a small hand-labelled set and report Spearman correlation.
- The token system is a simple signed token for the demo API. Use a vetted JWT library and HTTPS in production.

## Ideas for next steps

- Evaluate ranking quality on labelled resumes
- Students apply to recruiter jobs and see their match before applying
- Move SQLite to PostgreSQL, then add Docker and a free deployment
