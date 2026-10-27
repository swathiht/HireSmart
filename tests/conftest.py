import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SAMPLES = ROOT / "sample_data"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets a fresh empty database and no LLM."""
    monkeypatch.setenv("HIRESMART_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from app.db.database import init_db
    init_db()


@pytest.fixture
def jd_text():
    return (SAMPLES / "job_description.txt").read_text()


@pytest.fixture
def sample_files():
    return [(p.name, p.read_bytes()) for p in sorted((SAMPLES / "resumes").glob("*.txt"))]
