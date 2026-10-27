"""HireSmart - Streamlit front end (student and recruiter sides).

Run from the project root:   streamlit run frontend/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from app.auth.auth import AuthError, login, register  # noqa: E402
from app.core.jd_parser import parse_jd  # noqa: E402
from app.core.llm import llm_available  # noqa: E402
from app.core.question_gen import CATEGORY_LABELS  # noqa: E402
from app.core.resume_parser import extract_text, parse_resume  # noqa: E402
from app.core.scorer import score_resume  # noqa: E402
from app.core.skills import group_by_category  # noqa: E402
from app.db import database as db  # noqa: E402
from app.recruiter import interview_kit as kit  # noqa: E402
from app.recruiter.ranking import add_resume_files, compare_candidates, create_job, rank_candidates  # noqa: E402
from app.reports.pdf import interview_kit_pdf, student_report_pdf  # noqa: E402
from app.student.ats import ats_report  # noqa: E402
from app.student.improve import improve_bullets  # noqa: E402
from app.student.practice import check_mcq, student_mcqs, student_questions  # noqa: E402
from app.student.skill_gap import gap_report  # noqa: E402

SAMPLES = ROOT / "sample_data"
DIFF_ICON = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}

st.set_page_config(page_title="HireSmart", page_icon="🎯", layout="wide")
db.init_db()


# --------------------------------------------------------------------------- shared helpers
def bar_chart(values: dict[str, float], title: str, color: str = "#1f4e79") -> go.Figure:
    fig = go.Figure(go.Bar(x=list(values.values()), y=list(values.keys()), orientation="h", marker_color=color,
                           text=[f"{v:.0f}" for v in values.values()], textposition="outside"))
    fig.update_layout(title=title, xaxis=dict(range=[0, 110]), yaxis=dict(autorange="reversed"), height=260,
                      margin=dict(l=10, r=10, t=40, b=10))
    return fig


def show_questions(questions: list[dict], deletable: bool = False, key_prefix: str = "q") -> None:
    for i, q in enumerate(questions, 1):
        label = f"{DIFF_ICON.get(q.get('difficulty'), '⚪')} {i}. {q['question']}"
        with st.expander(label):
            st.caption(f"{q.get('category_label', q.get('category', ''))}  ·  {q.get('difficulty', '')}"
                       + ("  ·  added by you" if q.get("is_custom") else ""))
            if q.get("why"):
                st.markdown(f"**Why it's asked:** {q['why']}")
            if q.get("evidence"):
                st.markdown(f"**Resume evidence:** _{q['evidence']}_")
            if q.get("rubric"):
                st.markdown("**A good answer covers:**\n" + "\n".join(f"- {r}" for r in q["rubric"]))
            if q.get("follow_up"):
                st.markdown(f"**Follow-up:** {q['follow_up']}")
            if deletable and q.get("_id"):
                if st.button("Remove this question", key=f"{key_prefix}_del_{q['_id']}"):
                    kit.remove_question(q["_id"])
                    st.rerun()


def read_upload(uploaded) -> dict | None:
    try:
        parsed = parse_resume(extract_text(uploaded.getvalue(), uploaded.name))
    except Exception as exc:
        st.error(f"Could not read that file: {exc}")
        return None
    if parsed["word_count"] < 30:
        st.error("Very little text found. If this is a scanned PDF, please upload a text-based PDF or DOCX.")
        return None
    return parsed


# --------------------------------------------------------------------------- auth screen
def auth_screen() -> None:
    st.title("🎯 HireSmart")
    st.caption("AI resume analysis for students · smart shortlisting and interview kits for recruiters")
    tab_login, tab_reg = st.tabs(["Log in", "Create account"])
    with tab_login:
        with st.form("login"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in"):
                try:
                    st.session_state.user = login(email, pw)
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
    with tab_reg:
        with st.form("register"):
            name = st.text_input("Full name")
            email = st.text_input("Email", key="reg_email")
            pw = st.text_input("Password (min 8 characters)", type="password", key="reg_pw")
            role = st.radio("I am a…", ["student", "recruiter"], horizontal=True)
            if st.form_submit_button("Create account"):
                try:
                    register(email, name, pw, role)
                    st.session_state.user = login(email, pw)
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
    st.info("Tip: use the sample resumes and sample job description inside the app. Please do not upload real people's resumes to a shared demo.")


# --------------------------------------------------------------------------- student side
def student_ui(user: dict) -> None:
    st.header("🎓 Student workspace")
    ss = st.session_state

    if "s_resume" not in ss:
        ss.s_resume = db.latest_resume_for_user(user["id"])
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1 · Your resume")
        up = st.file_uploader("Upload PDF, DOCX or TXT", type=["pdf", "docx", "txt"], key="s_upload")
        if up and ss.get("s_upload_name") != (up.name, up.size):
            parsed = read_upload(up)
            if parsed:
                parsed["_id"] = db.save_resume(user["id"], parsed, up.name)
                ss.s_resume = parsed
                ss.s_upload_name = (up.name, up.size)
                ss.pop("s_result", None)
        if st.button("Use a sample resume"):
            parsed = parse_resume((SAMPLES / "resumes" / "asha_rao.txt").read_text())
            parsed["_id"] = db.save_resume(user["id"], parsed, "asha_rao.txt")
            ss.s_resume = parsed
            ss.pop("s_result", None)
        if ss.s_resume:
            r = ss.s_resume
            st.success(f"Loaded: **{r['name'] or 'your resume'}** · {len(r['skills'])} skills · {len(r['projects'])} projects")
    with c2:
        st.subheader("2 · Target job")
        if st.button("Load sample job description"):
            ss.s_jd = (SAMPLES / "job_description.txt").read_text()
        jd_text = st.text_area("Paste the job description", key="s_jd", height=210)

    if st.button("Analyze my resume", type="primary", disabled=not (ss.s_resume and jd_text.strip())):
        resume, jd = ss.s_resume, parse_jd(jd_text)
        with st.spinner("Analysing…"):
            ss.s_result = {
                "jd": jd, "score": score_resume(resume, jd), "ats": ats_report(resume, jd), "gap": gap_report(resume, jd),
                "improve": improve_bullets(resume, jd), "questions": student_questions(resume, jd, n=8),
                "mcqs": student_mcqs(resume, jd, n=5), "seed": 0,
            }
    res = ss.get("s_result")
    if not res:
        st.caption("Upload a resume, add a job description and click **Analyze**.")
        return

    resume, jd = ss.s_resume, res["jd"]
    t_over, t_ats, t_gap, t_imp, t_q, t_mcq, t_pdf = st.tabs(
        ["Overview", "ATS score", "Skill gap", "Improve bullets", "Interview questions", "MCQ practice", "Report"])

    with t_over:
        m1, m2, m3 = st.columns(3)
        m1.metric("Job match", f"{res['score']['overall']}/100")
        m2.metric("ATS score", f"{res['ats']['overall']}/100")
        m3.metric("Skill coverage", f"{res['gap']['coverage']}%")
        st.write(res["score"]["explanation"])
        st.plotly_chart(bar_chart(res["score"]["breakdown"], "Match breakdown"), use_container_width=True)
        if jd.get("role"):
            st.caption(f"Detected role: {jd['role']} · level: {jd['level']}")

    with t_ats:
        st.write(res["ats"]["summary"])
        for s in res["ats"]["sections"]:
            st.progress(min(1.0, s["score"] / s["max"]), text=f"{s['name']}: {s['score']}/{s['max']}")
            for tip in s["tips"]:
                st.caption("• " + tip)

    with t_gap:
        g = res["gap"]
        st.write(f"**Matched skills:** {', '.join(g['matched']) or 'none yet'}")
        if not g["gaps"]:
            st.success("You cover every skill in this job description.")
        for gap in g["gaps"]:
            with st.expander(f"{'🔴' if gap['type'] == 'required' else '🟡'} {gap['skill']} ({gap['type']})"):
                if gap["you_already_have"]:
                    st.write("You already have related skills: " + ", ".join(gap["you_already_have"]))
                st.markdown(f"**What to learn:** {gap['what_to_learn']}")
                st.markdown(f"**Mini project:** {gap['mini_project']}")
        st.caption("Only add a skill to your resume once you have actually used it.")

    with t_imp:
        if not res["improve"]:
            st.success("No weak bullets found.")
        for it in res["improve"]:
            st.markdown(f"**Before:** {it['original']}")
            st.markdown(f"**After:** {it['suggestion']}")
            st.caption("Issues: " + "; ".join(it["issues"]) + f"  ·  generated by {it['source']}")
            st.divider()
        st.caption("Replace placeholders like [add result: …] with real numbers. Never invent results.")

    with t_q:
        c1, c2, c3 = st.columns(3)
        focus = c1.selectbox("Focus", ["all", "technical", "project", "hr"])
        diff = c2.selectbox("Difficulty", ["mixed", "easy", "medium", "hard"])
        n = c3.slider("How many", 4, 14, 8)
        if st.button("Generate new set"):
            res["seed"] += 1
            res["questions"] = student_questions(resume, jd, n=n, focus=focus, difficulty=None if diff == "mixed" else diff,
                                                 seed=res["seed"])
        show_questions(res["questions"], key_prefix="sq")

    with t_mcq:
        if st.button("New MCQ set"):
            res["seed"] += 1
            res["mcqs"] = student_mcqs(resume, jd, n=5, seed=res["seed"])
        for i, m in enumerate(res["mcqs"]):
            choice = st.radio(f"Q{i + 1}. {m['question']}", m["options"], index=None, key=f"mcq_{res['seed']}_{i}")
            st.caption(f"Topic: {m['skill']}")
            if choice is not None:
                fb = check_mcq(m, choice)
                (st.success if fb["correct"] else st.error)(fb["feedback"])
            st.divider()

    with t_pdf:
        pdf = student_report_pdf(resume, jd, res["score"], res["ats"], res["gap"], res["improve"], res["questions"], res["mcqs"])
        st.download_button("⬇️ Download PDF report", pdf, file_name="hiresmart_report.pdf", mime="application/pdf")


# --------------------------------------------------------------------------- recruiter side
def render_resume(r: dict) -> None:
    st.subheader(r["name"] or "Candidate")
    st.caption(" · ".join(x for x in [r["email"], r["phone"], *r["links"]] if x))
    if r.get("cgpa"):
        st.write(f"**CGPA:** {r['cgpa']}")
    st.markdown("**Skills**")
    for cat, skills in group_by_category(r["skills"]).items():
        st.markdown(f"- *{cat}:* {', '.join(skills)}")
    for title, items in [("Projects", r["projects"]), ("Experience", r["experience"])]:
        if items:
            st.markdown(f"**{title}**")
            for p in items:
                st.markdown(f"**{p['title']}** {('· ' + ', '.join(p['tech'])) if p['tech'] else ''} {('· ' + p.get('dates', '')) if p.get('dates') else ''}")
                for b in p["bullets"]:
                    st.markdown(f"- {b}")
    if r["publications"]:
        st.markdown("**Publications**")
        st.write(" ".join(r["publications"]))
    with st.expander("Full resume text"):
        st.text(r["raw_text"])


def candidate_page(job_id: int, resume_id: int, blind: bool) -> None:
    view = kit.candidate_view(resume_id, job_id)
    left, right = st.columns([1, 1])
    with left:
        if blind:
            st.info("Blind screening is on: name, contact and education are hidden.")
            hidden = dict(view["resume"], name="Candidate", email="", phone="", links=[], cgpa=None, raw_text="(hidden)")
            hidden["publications"] = []
            render_resume(hidden)
        else:
            render_resume(view["resume"])
    with right:
        st.metric("Match with job", f"{view['score']['overall']}%")
        st.write(view["score"]["explanation"])
        st.plotly_chart(bar_chart(view["score"]["breakdown"], "Score breakdown"), use_container_width=True)
        st.markdown("**Strengths:** " + (", ".join(view["strengths"]) or "—"))
        st.markdown("**Gaps vs job:** " + (", ".join(view["gaps"]) or "none"))
        st.divider()
        st.subheader("Interview questions")
        c1, c2, c3 = st.columns(3)
        focus = c1.selectbox("Focus", ["all", "technical", "project", "hr"], key=f"focus_{resume_id}")
        diff = c2.selectbox("Difficulty", ["mixed", "easy", "medium", "hard"], key=f"diff_{resume_id}")
        n = c3.slider("Questions", 4, 14, 8, key=f"n_{resume_id}")
        if st.button("Generate questions" if not view["questions"] else "Regenerate questions", type="primary", key=f"gen_{resume_id}"):
            seed = st.session_state.get("kit_seed", 0) + 1
            st.session_state.kit_seed = seed
            kit.generate_kit(resume_id, job_id, n=n, focus=focus, difficulty=None if diff == "mixed" else diff, seed=seed)
            st.rerun()
        show_questions(view["questions"], deletable=True, key_prefix=f"kq{resume_id}")
        with st.expander("➕ Add your own question"):
            with st.form(f"custom_{resume_id}", clear_on_submit=True):
                text = st.text_area("Question")
                cat = st.selectbox("Category", list(CATEGORY_LABELS), format_func=CATEGORY_LABELS.get)
                if st.form_submit_button("Add") and text.strip():
                    kit.add_custom(resume_id, job_id, text, cat)
                    st.rerun()
        if view["questions"]:
            name = "Candidate" if blind else (view["resume"]["name"] or "Candidate")
            pdf = interview_kit_pdf(name, view["job"]["title"], view["score"], view["strengths"], view["gaps"], view["questions"])
            st.download_button("⬇️ Download interview kit (PDF)", pdf, file_name="interview_kit.pdf", mime="application/pdf")


def recruiter_ui(user: dict) -> None:
    st.header("🧑‍💼 Recruiter workspace")
    jobs = db.list_jobs(user["id"])

    with st.expander("➕ Create a new job", expanded=not jobs):
        with st.form("new_job"):
            title = st.text_input("Job title")
            jd_text = st.text_area("Job description", value="", height=180, key="r_jd_new",
                                   placeholder="Paste the job description. Skills are extracted automatically.")
            if st.form_submit_button("Create job"):
                try:
                    st.session_state.r_job = create_job(user["id"], title, jd_text)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if st.button("Use the sample job description"):
            st.session_state.r_job = create_job(user["id"], "AI/ML Engineer (Working Student)", (SAMPLES / "job_description.txt").read_text())
            st.rerun()

    if not jobs:
        st.caption("Create a job to start.")
        return
    ids = [j["id"] for j in jobs]
    default = ids.index(st.session_state.get("r_job")) if st.session_state.get("r_job") in ids else 0
    job_id = st.selectbox("Job", ids, index=default, format_func=lambda i: next(j["title"] for j in jobs if j["id"] == i))
    st.session_state.r_job = job_id
    job = db.get_job(job_id)
    with st.expander("Skills extracted from the job description"):
        st.write("**Required:** " + (", ".join(job["required_skills"]) or "—"))
        st.write("**Preferred:** " + (", ".join(job["preferred_skills"]) or "—"))
        st.write(f"**Level:** {job['level']}")

    st.subheader("Resumes")
    files = st.file_uploader("Upload resumes (PDF, DOCX, TXT) — multiple allowed", type=["pdf", "docx", "txt"],
                             accept_multiple_files=True, key=f"r_files_{job_id}")
    c1, c2 = st.columns(2)
    if c1.button("Process uploaded resumes", disabled=not files):
        with st.spinner("Parsing and scoring…"):
            out = add_resume_files(user["id"], job_id, [(f.name, f.getvalue()) for f in files])
        st.success(f"Added {len(out['added'])} resume(s).")
        for e in out["errors"]:
            st.warning(f"{e['filename']}: {e['error']}")
    if c2.button("Load 5 sample resumes"):
        batch = [(p.name, p.read_bytes()) for p in sorted((SAMPLES / "resumes").glob("*.txt"))]
        out = add_resume_files(user["id"], job_id, batch)
        st.success(f"Added {len(out['added'])} sample resumes.")

    st.subheader("Ranked shortlist")
    f1, f2, f3, f4, f5 = st.columns([1, 2, 1, 1, 1])
    min_score = f1.slider("Min match %", 0, 100, 0)
    need = f2.multiselect("Must have skills", sorted(set(job["required_skills"] + job["preferred_skills"])))
    min_cgpa = f3.number_input("Min CGPA", 0.0, 10.0, 0.0, 0.1)
    kw = f4.text_input("Keyword")
    blind = f5.toggle("Blind screening", help="Hides name, contact details and CGPA")
    ranked = rank_candidates(job_id, min_score, need or None, min_cgpa or None, kw, blind)
    if not ranked:
        st.info("No candidates yet (or none match the filters).")
        return
    df = pd.DataFrame([{
        "Rank": r["rank"], "Candidate": r["name"], "Match %": r["match"],
        "Matched required": ", ".join(r["matched_required"]), "Missing required": ", ".join(r["missing_required"]),
        "CGPA": r["cgpa"], "Why": r["reason"]} for r in ranked])
    st.dataframe(df, hide_index=True, use_container_width=True,
                 column_config={"Match %": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%.0f")})
    st.download_button("⬇️ Export shortlist (CSV)", df.to_csv(index=False), file_name="shortlist.csv", mime="text/csv")

    with st.expander("Compare 2–3 candidates side by side"):
        picks = st.multiselect("Candidates", [r["resume_id"] for r in ranked], max_selections=3,
                               format_func=lambda i: next(r["name"] for r in ranked if r["resume_id"] == i))
        if len(picks) >= 2:
            cmp = compare_candidates(job_id, picks)
            cols = st.columns(len(cmp))
            for col, c in zip(cols, cmp):
                nm = next(r["name"] for r in ranked if r["resume_id"] == c["resume_id"])
                col.markdown(f"**{nm}**")
                col.metric("Match", f"{c['match']}%")
                col.write("Missing: " + (", ".join(c["missing_required"]) or "none"))
                col.write("Skills: " + ", ".join(c["skills"][:12]))

    st.subheader("Candidate page")
    chosen = st.selectbox("Open candidate", [r["resume_id"] for r in ranked],
                          format_func=lambda i: next(f"#{r['rank']} {r['name']} ({r['match']}%)" for r in ranked if r["resume_id"] == i))
    candidate_page(job_id, chosen, blind)


# --------------------------------------------------------------------------- app
def main() -> None:
    user = st.session_state.get("user")
    with st.sidebar:
        st.markdown("### 🎯 HireSmart")
        if user:
            st.write(f"**{user['name']}**  \n{user['role'].title()}")
            if st.button("Log out"):
                st.session_state.clear()
                st.rerun()
        st.caption("Question engine: " + ("LLM (API key found)" if llm_available() else "built-in (free, offline)"))
    if not user:
        auth_screen()
    elif user["role"] == "student":
        student_ui(user)
    else:
        recruiter_ui(user)


main()
