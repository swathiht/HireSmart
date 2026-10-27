"""Headless UI tests using Streamlit's AppTest (no browser needed)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "frontend" / "streamlit_app.py")


def _app():
    return AppTest.from_file(APP, default_timeout=60).run()


def _btn(at, label):
    return next(b for b in at.button if b.label == label)


def _register(at, role, email):
    at.text_input(key="reg_email").set_value(email)
    at.text_input(key="reg_pw").set_value("password123")
    # form text input without a key: the first one in the register form is the name
    names = [t for t in at.text_input if t.label == "Full name"]
    names[0].set_value("Test User")
    at.radio[0].set_value(role)
    next(b for b in at.button if b.label == "Create account").click()
    return at.run()


def test_login_screen_and_validation():
    at = _app()
    assert not at.exception and at.title[0].value.endswith("HireSmart")
    next(b for b in at.button if b.label == "Log in").click()
    at.run()
    assert any("Incorrect email or password" in e.value for e in at.error)


def test_student_full_flow():
    at = _register(_app(), "student", "stu@example.com")
    assert not at.exception, at.exception
    assert at.header[0].value.endswith("Student workspace")
    _btn(at, "Use a sample resume").click(); at.run()
    _btn(at, "Load sample job description").click(); at.run()
    _btn(at, "Analyze my resume").click(); at.run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 7
    assert [m.label for m in at.metric][:3] == ["Job match", "ATS score", "Skill coverage"]
    # instant MCQ feedback
    radio = next(r for r in at.radio if r.label.startswith("Q1."))
    radio.set_value(radio.options[0]); at.run()
    assert at.success or at.error
    # regenerate questions
    _btn(at, "Generate new set").click(); at.run()
    assert not at.exception, at.exception


def test_recruiter_full_flow():
    at = _register(_app(), "recruiter", "rec@example.com")
    assert not at.exception, at.exception
    assert at.header[0].value.endswith("Recruiter workspace")
    _btn(at, "Use the sample job description").click(); at.run()
    _btn(at, "Load 5 sample resumes").click(); at.run()
    assert not at.exception, at.exception
    assert len(at.dataframe[0].value) == 5
    _btn(at, "Generate questions").click(); at.run()
    assert not at.exception, at.exception
    assert len(at.expander) >= 8                      # question cards on the candidate page
    at.toggle[0].set_value(True); at.run()            # blind screening
    assert not at.exception, at.exception
    assert all(str(n).startswith("Candidate") for n in at.dataframe[0].value["Candidate"])


def test_role_separation():
    # a student never sees the recruiter workspace
    at = _register(_app(), "student", "only@example.com")
    assert not any("Recruiter workspace" in h.value for h in at.header)
