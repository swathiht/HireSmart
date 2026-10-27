"""Skill dictionary with categories and aliases.

Each canonical skill maps to a category and a list of aliases (lower-case).
`extract_skills(text)` returns the canonical names found in free text.
"""
from __future__ import annotations

import re
from functools import lru_cache

# canonical name -> (category, [aliases])
SKILLS: dict[str, tuple[str, list[str]]] = {
    # Languages
    "Python": ("Languages", ["python", "python3", "py"]),
    "Java": ("Languages", ["java", "core java"]),
    "C": ("Languages", ["c programming", "c language"]),
    "C++": ("Languages", ["c++", "cpp"]),
    "JavaScript": ("Languages", ["javascript", "js", "ecmascript", "es6"]),
    "TypeScript": ("Languages", ["typescript", "ts"]),
    "SQL": ("Languages", ["sql", "structured query language"]),
    "HTML/CSS": ("Languages", ["html", "css", "html5", "css3", "html/css"]),
    "R": ("Languages", ["r programming", "r language"]),
    "Bash": ("Languages", ["bash", "shell scripting", "shell"]),
    # ML / AI
    "Machine Learning": ("AI/ML", ["machine learning", "ml"]),
    "Deep Learning": ("AI/ML", ["deep learning", "dl", "neural networks", "neural network"]),
    "NLP": ("AI/ML", ["nlp", "natural language processing", "text mining"]),
    "Computer Vision": ("AI/ML", ["computer vision", "cv", "image processing", "image classification"]),
    "TensorFlow": ("AI/ML", ["tensorflow", "tf"]),
    "Keras": ("AI/ML", ["keras"]),
    "PyTorch": ("AI/ML", ["pytorch", "torch"]),
    "Scikit-learn": ("AI/ML", ["scikit-learn", "sklearn", "scikit learn"]),
    "XGBoost": ("AI/ML", ["xgboost", "xgb", "gradient boosting"]),
    "Transformers": ("AI/ML", ["transformers", "hugging face", "huggingface", "bert"]),
    "spaCy": ("AI/ML", ["spacy"]),
    "SentenceTransformers": ("AI/ML", ["sentencetransformers", "sentence-transformers", "sentence transformers", "sbert"]),
    "LLMs": ("AI/ML", ["llm", "llms", "large language model", "large language models", "gpt", "generative ai", "genai"]),
    "RAG": ("AI/ML", ["rag", "retrieval augmented generation", "retrieval-augmented generation"]),
    "LangChain": ("AI/ML", ["langchain", "llamaindex"]),
    "Prompt Engineering": ("AI/ML", ["prompt engineering", "prompting"]),
    "Vector Databases": ("AI/ML", ["vector database", "vector databases", "faiss", "chroma", "pinecone", "pgvector"]),
    "TF-IDF": ("AI/ML", ["tf-idf", "tfidf"]),
    "OpenCV": ("AI/ML", ["opencv", "cv2"]),
    # Data
    "Pandas": ("Data", ["pandas"]),
    "NumPy": ("Data", ["numpy"]),
    "Matplotlib": ("Data", ["matplotlib"]),
    "Seaborn": ("Data", ["seaborn"]),
    "Plotly": ("Data", ["plotly"]),
    "Data Analysis": ("Data", ["data analysis", "data analytics", "eda", "exploratory data analysis"]),
    "Data Visualization": ("Data", ["data visualization", "data visualisation", "dashboards"]),
    "Power BI": ("Data", ["power bi", "powerbi"]),
    "Tableau": ("Data", ["tableau"]),
    "Excel": ("Data", ["excel", "ms excel", "microsoft excel"]),
    "Statistics": ("Data", ["statistics", "statistical analysis"]),
    # Backend / web
    "FastAPI": ("Backend", ["fastapi"]),
    "Flask": ("Backend", ["flask"]),
    "Django": ("Backend", ["django"]),
    "REST APIs": ("Backend", ["rest", "rest api", "rest apis", "restful", "api development"]),
    "Streamlit": ("Backend", ["streamlit"]),
    "Node.js": ("Backend", ["node.js", "nodejs", "node"]),
    "React": ("Backend", ["react", "reactjs", "react.js"]),
    # Databases
    "MySQL": ("Databases", ["mysql"]),
    "PostgreSQL": ("Databases", ["postgresql", "postgres"]),
    "MongoDB": ("Databases", ["mongodb", "mongo"]),
    "SQLite": ("Databases", ["sqlite"]),
    "DBMS": ("Databases", ["dbms", "database management", "databases"]),
    # Tools / DevOps
    "Git": ("Tools", ["git"]),
    "GitHub": ("Tools", ["github"]),
    "Docker": ("Tools", ["docker", "containers", "containerization", "containerisation"]),
    "Kubernetes": ("Tools", ["kubernetes", "k8s"]),
    "CI/CD": ("Tools", ["ci/cd", "cicd", "github actions", "jenkins", "continuous integration"]),
    "Linux": ("Tools", ["linux", "unix"]),
    "Jupyter": ("Tools", ["jupyter", "jupyter notebook", "colab"]),
    "AWS": ("Cloud", ["aws", "amazon web services", "ec2", "s3", "lambda"]),
    "GCP": ("Cloud", ["gcp", "google cloud"]),
    "Azure": ("Cloud", ["azure"]),
    "MLflow": ("Tools", ["mlflow"]),
    "PyMuPDF": ("Tools", ["pymupdf", "fitz"]),
    "ReportLab": ("Tools", ["reportlab"]),
    # Core CS
    "Data Structures & Algorithms": ("Core CS", ["data structures", "algorithms", "dsa", "data structures and algorithms", "data structures & algorithms"]),
    "Operating Systems": ("Core CS", ["operating systems", "operating system", "os concepts"]),
    "OOP": ("Core CS", ["oop", "oops", "object oriented", "object-oriented"]),
    "Computer Networks": ("Core CS", ["computer networks", "networking"]),
    "Software Testing": ("Core CS", ["pytest", "unit testing", "software testing", "junit"]),
    "Agile": ("Core CS", ["agile", "scrum"]),
}

# Short or ambiguous aliases that must match as whole tokens with case-sensitivity hints.
_AMBIGUOUS = {"c", "r", "py", "ts", "js", "tf", "dl", "ml", "cv", "os", "rest", "node", "shell", "react", "torch"}

CATEGORY_ORDER = ["Languages", "AI/ML", "Data", "Backend", "Databases", "Tools", "Cloud", "Core CS"]


@lru_cache(maxsize=1)
def _alias_index() -> list[tuple[str, re.Pattern]]:
    """Build (canonical, compiled pattern) pairs, longest aliases first."""
    pairs: list[tuple[str, str]] = []
    for canon, (_cat, aliases) in SKILLS.items():
        names = {canon.lower(), *aliases}
        for a in names:
            pairs.append((canon, a))
    pairs.sort(key=lambda p: -len(p[1]))
    compiled = []
    for canon, alias in pairs:
        esc = re.escape(alias)
        pat = re.compile(rf"(?<![A-Za-z0-9+#]){esc}(?![A-Za-z0-9+#])", re.IGNORECASE)
        compiled.append((canon, alias, pat))
    return compiled  # type: ignore[return-value]


def _ambiguous_ok(alias: str, text: str, match: re.Match) -> bool:
    """Short aliases like 'C' or 'R' only count when written the way skills are written."""
    if alias not in _AMBIGUOUS:
        return True
    raw = text[match.start():match.end()]
    # accept if it appears in a comma/pipe/slash separated list context or capitalised form
    if alias in {"c", "r"}:
        around = text[max(0, match.start() - 2): match.end() + 2]
        return raw == raw.upper() and bool(re.search(r"[,|/•:]\s*" + re.escape(raw) + r"\s*[,|/•]?", around + " "))
    if alias in {"ml", "dl", "cv", "os", "tf", "ts", "js", "py"}:
        return raw.lower() == raw or raw.upper() == raw
    return True


def extract_skills(text: str) -> list[str]:
    """Return canonical skill names found in `text` (ordered by first appearance)."""
    if not text:
        return []
    found: dict[str, int] = {}
    for canon, alias, pat in _alias_index():
        for m in pat.finditer(text):
            if not _ambiguous_ok(alias, text, m):
                continue
            pos = m.start()
            if canon not in found or pos < found[canon]:
                found[canon] = pos
    return [c for c, _ in sorted(found.items(), key=lambda kv: kv[1])]


def skill_counts(text: str) -> dict[str, int]:
    """How many times each canonical skill is mentioned (used as an importance signal)."""
    counts: dict[str, int] = {}
    for canon, alias, pat in _alias_index():
        for m in pat.finditer(text or ""):
            if _ambiguous_ok(alias, text, m):
                counts[canon] = counts.get(canon, 0) + 1
    return counts


def category_of(skill: str) -> str:
    return SKILLS.get(skill, ("Other", []))[0]


def group_by_category(skills: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for s in skills:
        grouped.setdefault(category_of(s), []).append(s)
    return {c: grouped[c] for c in CATEGORY_ORDER if c in grouped} | {
        c: v for c, v in grouped.items() if c not in CATEGORY_ORDER
    }


def related_skills(skill: str) -> list[str]:
    """Skills in the same category, used to say 'you have something similar'."""
    cat = category_of(skill)
    return [s for s, (c, _) in SKILLS.items() if c == cat and s != skill]
