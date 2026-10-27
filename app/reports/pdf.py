"""PDF reports with ReportLab: student report and recruiter interview kit."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ACCENT = colors.HexColor("#1f4e79")


def _t(text) -> str:
    """Escape for ReportLab and drop characters the built-in fonts cannot draw."""
    s = escape(str(text if text is not None else ""))
    return s.encode("cp1252", "replace").decode("cp1252")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], textColor=ACCENT, fontSize=20, spaceAfter=6),
        "h1": ParagraphStyle("h1", parent=base["Heading2"], textColor=ACCENT, spaceBefore=12, spaceAfter=4),
        "body": ParagraphStyle("b", parent=base["BodyText"], fontSize=10, leading=14),
        "small": ParagraphStyle("s", parent=base["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#444444")),
        "q": ParagraphStyle("q", parent=base["BodyText"], fontSize=10.5, leading=14, spaceBefore=8),
    }


def _table(rows, widths, header=True):
    tbl = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("FONTSIZE", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), ACCENT), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    tbl.setStyle(TableStyle(style))
    return tbl


def _doc(buf):
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)


def student_report_pdf(resume: dict, jd: dict, score: dict, ats: dict, gap: dict, improvements: list[dict],
                       questions: list[dict], mcqs: list[dict] | None = None) -> bytes:
    st, buf = _styles(), io.BytesIO()
    story = [Paragraph("HireSmart - Resume Analysis Report", st["title"]),
             Paragraph(_t(f"{resume.get('name') or 'Candidate'}  |  Target role: {jd.get('role') or 'see job description'}"), st["small"]),
             Spacer(1, 6)]

    story += [Paragraph("Summary", st["h1"]),
              Paragraph(f"Match score: <b>{score['overall']}/100</b>  |  ATS score: <b>{ats['overall']}/100</b>", st["body"]),
              Paragraph(_t(score["explanation"]), st["body"])]

    story.append(Paragraph("ATS breakdown", st["h1"]))
    rows = [["Section", "Score", "Tips"]] + [
        [Paragraph(_t(s["name"]), st["small"]), f"{s['score']}/{s['max']}", Paragraph(_t(" ".join(s["tips"])), st["small"])]
        for s in ats["sections"]]
    story.append(_table(rows, [38 * mm, 20 * mm, 116 * mm]))

    story.append(Paragraph("Skill gap analysis", st["h1"]))
    story.append(Paragraph(_t(f"Coverage of the job's skills: {gap['coverage']}%. Matched: {', '.join(gap['matched']) or 'none'}."), st["body"]))
    if gap["gaps"]:
        rows = [["Missing skill", "Type", "What to learn", "Mini project"]] + [
            [Paragraph(_t(g["skill"]), st["small"]), g["type"], Paragraph(_t(g["what_to_learn"]), st["small"]),
             Paragraph(_t(g["mini_project"]), st["small"])] for g in gap["gaps"][:10]]
        story.append(_table(rows, [30 * mm, 20 * mm, 60 * mm, 64 * mm]))

    if improvements:
        story.append(Paragraph("Resume bullet improvements", st["h1"]))
        for it in improvements:
            story.append(Paragraph(_t(f"Before: {it['original']}"), st["small"]))
            story.append(Paragraph(_t(f"After:  {it['suggestion']}"), st["body"]))
            story.append(Paragraph(_t("Issues: " + "; ".join(it["issues"])), st["small"]))
            story.append(Spacer(1, 4))

    if questions:
        story.append(Paragraph("Practice interview questions", st["h1"]))
        for i, q in enumerate(questions, 1):
            story.append(Paragraph(_t(f"{i}. [{q['category_label']} - {q['difficulty']}] {q['question']}"), st["q"]))
            story.append(Paragraph(_t("A good answer covers: " + "; ".join(q["rubric"])), st["small"]))

    if mcqs:
        story.append(Paragraph("MCQ practice", st["h1"]))
        for i, m in enumerate(mcqs, 1):
            story.append(Paragraph(_t(f"{i}. {m['question']}"), st["q"]))
            for o, letter in zip(m["options"], "ABCD"):
                story.append(Paragraph(_t(f"{letter}. {o}"), st["small"]))
            story.append(Paragraph(_t(f"Answer: {m['answer']}. {m.get('explanation', '')}"), st["small"]))

    _doc(buf).build(story)
    return buf.getvalue()


def interview_kit_pdf(candidate_name: str, job_title: str, score: dict, strengths: list[str], gaps: list[str],
                      questions: list[dict]) -> bytes:
    st, buf = _styles(), io.BytesIO()
    story = [Paragraph("Interview Kit", st["title"]),
             Paragraph(_t(f"Candidate: {candidate_name}  |  Position: {job_title}  |  Match: {score['overall']}%"), st["small"]),
             Spacer(1, 6),
             Paragraph("Fit summary", st["h1"]),
             Paragraph(_t(score["explanation"]), st["body"]),
             Paragraph(_t("Strengths: " + (", ".join(strengths) or "none identified")), st["body"]),
             Paragraph(_t("Gaps vs job: " + (", ".join(gaps) or "none")), st["body"]),
             Paragraph("Questions", st["h1"])]
    for i, q in enumerate(questions, 1):
        story.append(Paragraph(_t(f"{i}. [{q.get('category_label', q.get('category', ''))} | {q.get('difficulty', '')}] {q['question']}"), st["q"]))
        if q.get("why"):
            story.append(Paragraph(_t(f"Why asked: {q['why']}"), st["small"]))
        if q.get("evidence"):
            story.append(Paragraph(_t(f"Resume evidence: {q['evidence']}"), st["small"]))
        if q.get("rubric"):
            story.append(Paragraph(_t("Good answer covers: " + "; ".join(q["rubric"])), st["small"]))
        if q.get("follow_up"):
            story.append(Paragraph(_t(f"Follow-up: {q['follow_up']}"), st["small"]))
        story.append(Paragraph("Rating (1-5): ____    Notes: ______________________________", st["small"]))
    _doc(buf).build(story)
    return buf.getvalue()
