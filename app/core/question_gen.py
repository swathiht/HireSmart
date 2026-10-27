"""Interview question + MCQ generation, shared by the student and recruiter sides.

Two engines:
  * LLM (when ANTHROPIC_API_KEY is set) - grounded in the parsed resume + JD JSON.
  * Rule-based fallback - runs offline, free, and is deterministic (good for tests).

Every question has the same shape:
    {question, category, difficulty, why, evidence, rubric[3], follow_up}
"""
from __future__ import annotations

import json
import random
import re

from .llm import llm_available, llm_json
from .skills import related_skills

CATEGORIES = ["project", "technical", "gap", "verification", "hr"]
CATEGORY_LABELS = {
    "project": "Project deep-dive",
    "technical": "Technical",
    "gap": "Gap-probing",
    "verification": "Verification",
    "hr": "HR / Behavioural",
}
DEFAULT_MIX = {"project": 3, "technical": 2, "gap": 1, "verification": 1, "hr": 1}

# --------------------------------------------------------------------------- technical bank
TECH_BANK: dict[str, list[tuple[str, str, list[str]]]] = {
    "Python": [
        ("Explain the difference between a list, a tuple, a set and a dict, and when you would pick each.", "easy",
         ["Mutability and ordering differences", "Lookup/insert complexity", "A realistic use case for each"]),
        ("How do generators and decorators work in Python? Give an example of when you would use each.", "medium",
         ["Lazy evaluation / yield for generators", "Decorators wrap functions (higher-order functions)", "Concrete practical example"]),
    ],
    "SQL": [
        ("What is the difference between WHERE and HAVING, and between INNER and LEFT JOIN?", "easy",
         ["WHERE filters rows before grouping, HAVING after", "INNER keeps matches only, LEFT keeps all left rows", "Simple example query"]),
        ("How would you find the second-highest value in a table, and how would you speed up a slow query?", "medium",
         ["Subquery, window function or LIMIT/OFFSET approach", "Index usage and reading the query plan", "Avoiding SELECT * and unnecessary joins"]),
    ],
    "Machine Learning": [
        ("How do you detect and handle overfitting? Name at least three techniques.", "medium",
         ["Train vs validation gap", "Regularisation, dropout, early stopping, more data", "Cross-validation"]),
        ("Which metrics would you use for an imbalanced classification problem, and why is accuracy misleading there?", "medium",
         ["Precision, recall, F1, ROC-AUC / PR-AUC", "Accuracy rewards predicting the majority class", "Link to a real example"]),
    ],
    "Deep Learning": [
        ("What is transfer learning and when would you freeze versus fine-tune layers of a pre-trained network?", "medium",
         ["Reusing learned features", "Freeze when data is small / similar domain", "Fine-tune with low learning rate when more data is available"]),
        ("Explain backpropagation and the vanishing gradient problem in simple terms.", "hard",
         ["Chain rule to compute gradients", "Gradients shrink through deep layers / saturating activations", "ReLU, residual connections, normalisation as remedies"]),
    ],
    "NLP": [
        ("How does TF-IDF work, and how do contextual embeddings improve on it?", "medium",
         ["Term frequency x inverse document frequency", "TF-IDF ignores word order and context", "Embeddings capture semantics and context"]),
        ("How would you evaluate a text classification or semantic-search system?", "medium",
         ["Appropriate metrics (F1, MRR, recall@k)", "Labelled evaluation set / error analysis", "Baseline comparison"]),
    ],
    "Computer Vision": [
        ("How do convolutional layers extract features, and why use pooling?", "medium",
         ["Local filters and weight sharing", "Pooling reduces dimensions / adds invariance", "Hierarchy from edges to objects"]),
    ],
    "TensorFlow": [
        ("How do you build, train and save a model in TensorFlow/Keras, and how do you stop it overfitting?", "medium",
         ["Model definition, compile, fit", "Callbacks such as EarlyStopping / checkpointing", "Saving and reloading the model"]),
    ],
    "Keras": [
        ("What is the difference between the Sequential and Functional APIs in Keras?", "easy",
         ["Sequential is a linear stack", "Functional supports branching / multiple inputs", "When each is appropriate"]),
    ],
    "PyTorch": [
        ("Explain the PyTorch training loop and what autograd does.", "medium",
         ["Forward pass, loss, backward, optimiser step", "zero_grad before backward", "Autograd builds the computation graph"]),
    ],
    "Scikit-learn": [
        ("How do you build a leak-free preprocessing + model workflow in scikit-learn?", "medium",
         ["Pipelines / ColumnTransformer", "Fit transformers on training data only", "Cross-validation and hyper-parameter search"]),
    ],
    "XGBoost": [
        ("How does gradient boosting work, and which XGBoost hyper-parameters matter most?", "hard",
         ["Sequential trees correcting residuals", "learning_rate, max_depth, n_estimators, subsample", "Regularisation and early stopping"]),
    ],
    "Transformers": [
        ("Explain self-attention and why transformers replaced RNNs for most NLP tasks.", "hard",
         ["Queries/keys/values and attention weights", "Parallelism and long-range dependencies", "Cost: quadratic in sequence length"]),
    ],
    "LLMs": [
        ("What are the main limitations of LLMs in production and how do you reduce hallucinations?", "medium",
         ["Hallucination, cost, latency, context limits", "Grounding with retrieval (RAG), constrained output", "Evaluation and human review"]),
    ],
    "RAG": [
        ("Describe the components of a RAG pipeline and how you would evaluate retrieval quality.", "medium",
         ["Chunking, embeddings, vector store, retriever, generator", "Recall@k / MRR for retrieval, faithfulness for answers", "Failure modes such as bad chunking"]),
    ],
    "Pandas": [
        ("How do you handle missing values and merge two DataFrames in pandas?", "easy",
         ["isna / fillna / dropna choices and trade-offs", "merge vs concat and join types", "Checking the result shape"]),
    ],
    "NumPy": [
        ("Why is NumPy faster than Python lists, and what is broadcasting?", "easy",
         ["Contiguous typed memory, vectorised C operations", "Broadcasting rules with an example", "Avoiding Python loops"]),
    ],
    "Streamlit": [
        ("How does Streamlit's execution model work and how do you keep state between interactions?", "medium",
         ["Script reruns on each interaction", "st.session_state for state", "Caching with st.cache_data / cache_resource"]),
    ],
    "FastAPI": [
        ("What do Pydantic models give you in FastAPI, and how do you structure auth and error handling?", "medium",
         ["Validation and automatic docs", "Dependency injection for auth", "HTTPException / status codes"]),
    ],
    "Flask": [
        ("How is a Flask request handled, and how would you structure a larger Flask app?", "medium",
         ["Routing and request context", "Blueprints / app factory", "Configuration and testing"]),
    ],
    "REST APIs": [
        ("What makes an API RESTful, and how do you choose HTTP methods and status codes?", "easy",
         ["Resources, statelessness", "GET/POST/PUT/DELETE semantics", "Meaningful status codes (200/201/400/404)"]),
    ],
    "Docker": [
        ("What is the difference between a Docker image and a container, and how do you keep images small?", "medium",
         ["Image = template, container = running instance", "Slim base images, multi-stage builds", ".dockerignore and layer caching"]),
    ],
    "Git": [
        ("How do you resolve a merge conflict, and what is the difference between merge and rebase?", "medium",
         ["Identify conflict markers and resolve manually", "Merge keeps history, rebase rewrites it", "When not to rebase shared branches"]),
    ],
    "AWS": [
        ("Which AWS services would you use to host a small ML web app, and how do you keep costs and security under control?", "medium",
         ["Compute (EC2/ECS/Lambda) + storage (S3)", "IAM least privilege, secrets handling", "Budgets and alerts"]),
    ],
    "Data Structures & Algorithms": [
        ("When would you use a hash map versus a balanced tree, and what is the complexity of each operation?", "medium",
         ["Average O(1) vs O(log n)", "Ordering requirements", "Collision handling"]),
    ],
    "OOP": [
        ("Explain encapsulation, inheritance and polymorphism with an example from one of your projects.", "easy",
         ["Defines each principle correctly", "Concrete example", "Composition vs inheritance trade-off"]),
    ],
    "Operating Systems": [
        ("What is the difference between a process and a thread, and what causes a deadlock?", "medium",
         ["Memory sharing differences", "Four deadlock conditions", "Prevention strategies (ordering, timeouts)"]),
    ],
    "DBMS": [
        ("Explain normalisation and ACID properties with an example.", "medium",
         ["1NF/2NF/3NF reduce redundancy", "Atomicity, Consistency, Isolation, Durability", "Trade-off with performance"]),
    ],
    "JavaScript": [
        ("Explain closures and the event loop in JavaScript.", "medium",
         ["Closure captures lexical scope", "Call stack, task queue, microtasks", "Async/await with promises"]),
    ],
    "React": [
        ("How do state and props differ in React, and when would you use useEffect?", "easy",
         ["Props are inputs, state is internal", "useEffect for side effects with dependencies", "Avoiding unnecessary re-renders"]),
    ],
    "Vector Databases": [
        ("How does approximate nearest-neighbour search work, and how do you choose a vector store?", "hard",
         ["Index types such as HNSW / IVF", "Recall vs latency trade-off", "Scale, filtering and cost considerations"]),
    ],
}

GENERIC_TECH = (
    "Describe a concrete situation where you used {skill}. What problem did it solve and what would you do differently now?",
    "medium",
    ["Clear, specific example", "Understands why {skill} fit the problem", "Mentions limitations or alternatives"],
)

HR_BANK = {
    "teamwork": ("Tell me about a time you coordinated a team or event. How did you handle responsibilities and conflicts?",
                 ["Specific situation and your role", "Communication / delegation", "Result and what you learned"]),
    "pressure": ("Describe a time you had to deliver under a tight deadline, such as a hackathon. How did you prioritise?",
                 ["Prioritisation approach", "Handling setbacks", "Outcome and reflection"]),
    "learning": ("Tell me about a time you had to learn a new tool or concept quickly. How did you approach it?",
                 ["Structured learning method", "Applied it to something real", "Measurable result"]),
    "research": ("How did you approach publishing or presenting your research, and what feedback did you act on?",
                 ["Process from idea to paper", "Handling reviewer / peer feedback", "Lessons for future work"]),
    "motivation": ("Why are you interested in this role, and where do you want to grow in the next two years?",
                   ["Understands the role", "Honest, specific motivation", "Realistic growth plan"]),
}


# --------------------------------------------------------------------------- helpers
def _q(question, category, difficulty, why, evidence, rubric, follow_up) -> dict:
    return {
        "question": question,
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "difficulty": difficulty,
        "why": why,
        "evidence": evidence,
        "rubric": rubric[:3],
        "follow_up": follow_up,
    }


def _why(audience: str, recruiter_text: str, student_text: str) -> str:
    return recruiter_text if audience == "recruiter" else student_text


def _jd_skills(jd: dict) -> list[str]:
    return list(jd.get("required_skills", [])) + list(jd.get("preferred_skills", []))


def _snippet(text: str, n: int = 140) -> str:
    text = re.sub(r"[•\u2022\u25CF▪*]\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


# --------------------------------------------------------------------------- rule-based pieces
def _project_questions(resume: dict, jd: dict, audience: str) -> list[dict]:
    out: list[dict] = []
    jd_sk = set(_jd_skills(jd))
    projects = sorted(resume["projects"], key=lambda p: -len(set(p["skills"]) & jd_sk)) or []
    templates = [
        ("Walk me through '{t}'. What problem did it solve and what exactly was your contribution?", "easy",
         ["Clear problem statement", "Own contribution vs team/tutorial work", "Outcome or impact"],
         "What would you change if you rebuilt it from scratch?"),
        ("Why did you choose {s} for '{t}'? Which alternatives did you consider and why did you reject them?", "medium",
         ["Reasoned selection criteria", "Names realistic alternatives", "Trade-offs acknowledged"],
         "What limitation of {a} did you actually run into?"),
        ("What was the hardest technical problem in '{t}' and how did you debug or solve it?", "medium",
         ["Specific, genuine problem", "Systematic debugging approach", "What was learned"],
         "How would you prevent the same problem in the next project?"),
        ("If '{t}' had to handle 100x more data or users, what would break first and how would you fix it?", "hard",
         ["Identifies a real bottleneck", "Proposes concrete changes (batching, caching, async, DB)", "Considers cost / complexity"],
         "How would you measure that the fix worked?"),
    ]
    for i, p in enumerate(projects):
        t = p["title"] or "your project"
        evidence = _snippet(p["bullets"][0]) if p["bullets"] else _snippet(t)
        skills = [s for s in p["skills"] if s not in {"Python", "Git", "GitHub"}] or p["skills"]
        s_txt = " and ".join(skills[:2]) if skills else "that approach"
        a_txt = skills[0] if skills else "your approach"
        for j, (qt, diff, rub, fu) in enumerate(templates):
            if j == 1 and not skills:
                continue
            out.append(_q(
                qt.format(t=t, s=s_txt), "project", diff,
                _why(audience, f"Tests depth of ownership in '{t}'.",
                     f"Interviewers usually probe the projects you list; '{t}' is on your resume."),
                evidence, rub, fu.format(a=a_txt),
            ))
    # interleave so different projects come first
    by_template: dict[int, list[dict]] = {}
    order = []
    for idx, q in enumerate(out):
        by_template.setdefault(idx % 4, []).append(q)
    return out


def _technical_questions(resume: dict, jd: dict, audience: str) -> list[dict]:
    required = jd.get("required_skills", [])
    have = set(resume["skills"])
    ordered = [s for s in required if s in have] + [s for s in resume["skills"] if s not in required and s in set(_jd_skills(jd))]
    ordered += [s for s in resume["skills"] if s not in ordered]
    out: list[dict] = []
    for skill in ordered:
        items = TECH_BANK.get(skill)
        evidence = f"Skill '{skill}' is listed on the resume" + (" and required by the JD." if skill in required else ".")
        if items:
            for qt, diff, rub in items:
                out.append(_q(qt, "technical", diff,
                              _why(audience, f"Checks that the listed skill '{skill}' is backed by real understanding.",
                                   f"You list {skill}; expect fundamentals questions on it."),
                              evidence, rub, f"Where exactly have you applied this in practice?"))
        else:
            qt, diff, rub = GENERIC_TECH
            out.append(_q(qt.format(skill=skill), "technical", diff,
                          _why(audience, f"Validates hands-on use of {skill}.", f"{skill} is on your resume, so be ready to give an example."),
                          evidence, [r.format(skill=skill) for r in rub], "What would you do differently next time?"))
    return out


def _gap_questions(resume: dict, jd: dict, audience: str) -> list[dict]:
    have = set(resume["skills"])
    out = []
    for skill in jd.get("required_skills", []):
        if skill in have:
            continue
        near = [s for s in related_skills(skill) if s in have][:2]
        hint = f" You have related experience with {' and '.join(near)}." if near else ""
        out.append(_q(
            f"This role requires {skill}, which does not appear on your resume.{hint} Have you used it or something similar, and how quickly could you become productive?",
            "gap", "medium",
            _why(audience, f"Required skill '{skill}' is missing from the resume; probes transferable experience.",
                 f"The job needs {skill} and your resume does not show it; prepare an honest answer."),
            f"No mention of {skill}" + (f"; related: {', '.join(near)}" if near else ""),
            ["Honest about the gap", "Transferable experience or concrete learning plan", "Realistic timeline"],
            f"What is the first small project you would build to learn {skill}?",
        ))
    return out


_METRIC_RE = re.compile(r"(\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?\s?(?:x|ms|seconds|users|resumes|samples|images|records))", re.IGNORECASE)


def _verification_questions(resume: dict, audience: str) -> list[dict]:
    out = []
    for p in resume["projects"] + resume["experience"]:
        for b in p["bullets"]:
            m = _METRIC_RE.search(b)
            if m:
                out.append(_q(
                    f"In '{p['title']}' you mention {m.group(1)}. How was this measured: what data, which train/test split and which baseline did you compare against?",
                    "verification", "medium",
                    _why(audience, f"Verifies the claim '{m.group(1)}' is genuine and reproducible.",
                         f"Numbers on a resume ('{m.group(1)}') are a favourite interviewer follow-up."),
                    _snippet(b),
                    ["Describes the evaluation setup precisely", "Mentions split / cross-validation / leakage risk", "Compares with a baseline"],
                    "Would the number hold on completely unseen data? How could you check?",
                ))
    return out


def _hr_questions(resume: dict, jd: dict, audience: str) -> list[dict]:
    blob = " ".join(resume["achievements"] + resume["summary"].split(".")[:1]).lower() + " " + resume["raw_text"].lower()
    keys: list[tuple[str, str]] = []
    ach = " ".join(resume["achievements"]).lower()
    if re.search(r"organi[sz]ed|volunteer|club|coordinat|marathon|event", ach):
        keys.append(("teamwork", _snippet(" ".join(resume["achievements"]), 120)))
    if re.search(r"hackathon|competition|codefury|contest", ach):
        keys.append(("pressure", _snippet(" ".join(resume["achievements"]), 120)))
    if resume["publications"]:
        keys.append(("research", _snippet(" ".join(resume["publications"]), 120)))
    keys.append(("learning", "General question for every candidate"))
    keys.append(("motivation", f"Role: {jd.get('role') or 'the advertised position'}"))
    out = []
    for key, evidence in keys:
        qt, rub = HR_BANK[key]
        out.append(_q(qt, "hr", "easy",
                      _why(audience, f"Assesses {key} and communication.", f"A common behavioural question ({key}); prepare a STAR-style story."),
                      evidence, rub, "What would you do differently if it happened again?"))
    return out


def _rule_based(resume: dict, jd: dict, audience: str) -> dict[str, list[dict]]:
    return {
        "project": _project_questions(resume, jd, audience),
        "technical": _technical_questions(resume, jd, audience),
        "gap": _gap_questions(resume, jd, audience),
        "verification": _verification_questions(resume, audience),
        "hr": _hr_questions(resume, jd, audience),
    }


def _mix_for(n: int, focus: str) -> dict[str, int]:
    if focus == "technical":
        mix = {"project": 0.35, "technical": 0.4, "gap": 0.15, "verification": 0.1, "hr": 0.0}
    elif focus == "hr":
        mix = {"project": 0.2, "technical": 0.0, "gap": 0.1, "verification": 0.0, "hr": 0.7}
    elif focus == "project":
        mix = {"project": 0.6, "technical": 0.1, "gap": 0.1, "verification": 0.2, "hr": 0.0}
    else:
        total = sum(DEFAULT_MIX.values())
        mix = {k: v / total for k, v in DEFAULT_MIX.items()}
    counts = {k: int(round(v * n)) for k, v in mix.items()}
    # fix rounding so the counts add up to n
    while sum(counts.values()) < n:
        counts[max(mix, key=lambda k: mix[k] - counts[k] / max(n, 1))] += 1
    while sum(counts.values()) > n:
        k = max(counts, key=counts.get)
        counts[k] -= 1
    return counts


# --------------------------------------------------------------------------- LLM engine
def _compact_resume(resume: dict) -> dict:
    return {
        "name": resume["name"], "skills": resume["skills"], "education": [e["text"] for e in resume["education"]],
        "projects": [{"title": p["title"], "tech": p["tech"], "bullets": p["bullets"]} for p in resume["projects"]],
        "experience": [{"title": p["title"], "bullets": p["bullets"]} for p in resume["experience"]],
        "publications": resume["publications"], "achievements": resume["achievements"],
    }


def _llm_questions(resume: dict, jd: dict, audience: str, counts: dict[str, int], difficulty: str | None) -> list[dict] | None:
    who = "an experienced technical interviewer preparing questions for a recruiter" if audience == "recruiter" \
        else "an interview coach preparing a student for likely questions"
    prompt = f"""You are {who}.
Generate interview questions using ONLY facts present in the resume or required by the job. Never invent projects or skills.

Counts per category: {json.dumps(counts)}
Categories: project (deep-dive on their projects), technical (skills on the resume that matter for the job),
gap (JD-required skills missing from the resume), verification (check numeric claims), hr (behavioural).
{('All questions must be ' + difficulty + ' difficulty.') if difficulty else 'Mix easy, medium and hard.'}

RESUME JSON:
{json.dumps(_compact_resume(resume))[:6000]}

JOB JSON:
{json.dumps({k: jd.get(k) for k in ('role','level','required_skills','preferred_skills')})}

Return ONLY a JSON list. Each item has keys:
question, category, difficulty (easy|medium|hard), why (one sentence), evidence (resume text it is based on),
rubric (list of exactly 3 short points a good answer covers), follow_up (one question)."""
    data = llm_json(prompt)
    if not isinstance(data, list):
        return None
    out = []
    for item in data:
        try:
            cat = item["category"] if item["category"] in CATEGORIES else "technical"
            diff = item.get("difficulty", "medium")
            out.append(_q(item["question"], cat, diff if diff in {"easy", "medium", "hard"} else "medium",
                          item.get("why", ""), item.get("evidence", ""),
                          list(item.get("rubric", []))[:3], item.get("follow_up", "")))
        except (KeyError, TypeError):
            continue
    return out or None


# --------------------------------------------------------------------------- public API
def generate_questions(resume: dict, jd: dict, audience: str = "recruiter", n: int = 8, focus: str = "all",
                       difficulty: str | None = None, use_llm: bool = True, seed: int = 0) -> list[dict]:
    """Return `n` interview questions. `audience` is 'recruiter' or 'student'. `focus` in all|technical|hr|project."""
    counts = _mix_for(n, focus)
    if use_llm and llm_available():
        got = _llm_questions(resume, jd, audience, counts, difficulty)
        if got:
            return got[:n]

    pools = _rule_based(resume, jd, audience)
    rng = random.Random(seed)
    chosen: list[dict] = []
    leftover: list[dict] = []
    for cat in CATEGORIES:
        pool = pools[cat]
        if difficulty:
            preferred = [q for q in pool if q["difficulty"] == difficulty]
            pool = preferred + [q for q in pool if q not in preferred]
        if cat == "project":  # keep project order stable but spread across projects
            pool = _spread_projects(pool)
        take = counts.get(cat, 0)
        chosen.extend(pool[:take])
        leftover.extend(pool[take:])
    # top up from other categories if a pool was too small
    need = n - len(chosen)
    if need > 0:
        rng.shuffle(leftover)
        chosen.extend(leftover[:need])
    order = {c: i for i, c in enumerate(CATEGORIES)}
    chosen.sort(key=lambda q: order[q["category"]])
    return chosen[:n]


def _spread_projects(pool: list[dict]) -> list[dict]:
    """Round-robin across projects so the first picks cover different projects."""
    groups: dict[str, list[dict]] = {}
    for q in pool:
        title = re.search(r"'([^']+)'", q["question"])
        groups.setdefault(title.group(1) if title else "", []).append(q)
    out: list[dict] = []
    while any(groups.values()):
        for k in list(groups):
            if groups[k]:
                out.append(groups[k].pop(0))
    return out


# --------------------------------------------------------------------------- MCQ bank
MCQ_BANK: dict[str, list[dict]] = {
    "Python": [
        {"q": "What does len({1, 2, 2, 3}) return?", "options": ["2", "3", "4", "Error"], "answer": "3",
         "why": "A set stores unique elements, so the duplicate 2 is removed leaving {1, 2, 3}."},
        {"q": "Which of these Python types is immutable?", "options": ["list", "dict", "tuple", "set"], "answer": "tuple",
         "why": "Tuples cannot be modified after creation; lists, dicts and sets can."},
    ],
    "SQL": [
        {"q": "Which clause filters rows AFTER aggregation?", "options": ["WHERE", "HAVING", "GROUP BY", "ORDER BY"], "answer": "HAVING",
         "why": "WHERE filters rows before grouping; HAVING filters the groups produced by GROUP BY."},
        {"q": "Which JOIN keeps every row from the left table even when there is no match?", "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "SELF JOIN"], "answer": "LEFT JOIN",
         "why": "LEFT JOIN returns all left rows and fills unmatched right columns with NULL."},
    ],
    "Machine Learning": [
        {"q": "A model scores 99% on training data but 70% on validation data. What is the most likely problem?", "options": ["Underfitting", "Overfitting", "A perfect model", "Too little training time"], "answer": "Overfitting",
         "why": "A large train/validation gap means the model memorised the training data instead of generalising."},
        {"q": "Which metric is generally more informative than accuracy for a heavily imbalanced classification task?", "options": ["Accuracy", "F1-score", "Mean squared error", "R-squared"], "answer": "F1-score",
         "why": "F1 balances precision and recall, so predicting only the majority class is not rewarded."},
    ],
    "Deep Learning": [
        {"q": "What is the main purpose of an activation function such as ReLU?", "options": ["Introduce non-linearity", "Reduce dataset size", "Normalise labels", "Speed up disk reads"], "answer": "Introduce non-linearity",
         "why": "Without non-linear activations, stacked layers collapse into a single linear transformation."},
        {"q": "Transfer learning means:", "options": ["Training from random weights", "Reusing a pre-trained model's learned features for a new task", "Copying data between servers", "Converting a model to another framework"], "answer": "Reusing a pre-trained model's learned features for a new task",
         "why": "Pre-trained feature extractors such as ResNet can be reused so you need less data and training time."},
    ],
    "NLP": [
        {"q": "TF-IDF gives a LOWER weight to words that:", "options": ["Appear in many documents", "Appear only once in a document", "Are long", "Start a sentence"], "answer": "Appear in many documents",
         "why": "The inverse document frequency part penalises terms that are common across the corpus."},
        {"q": "Which of these produces context-dependent word embeddings?", "options": ["One-hot encoding", "Bag of words", "BERT", "TF-IDF"], "answer": "BERT",
         "why": "BERT's embedding for a word changes with its surrounding sentence; the others ignore context."},
    ],
    "RAG": [
        {"q": "In a RAG pipeline, what is retrieved before the LLM generates an answer?", "options": ["Relevant document chunks", "Model weights", "Training labels", "GPU drivers"], "answer": "Relevant document chunks",
         "why": "Retrieved chunks are added to the prompt so the answer is grounded in your own documents."},
    ],
    "Docker": [
        {"q": "What is the difference between a Docker image and a container?", "options": ["They are the same thing", "An image is a read-only template; a container is a running instance of it", "A container is a template; an image is a running process", "Images only run on Linux"], "answer": "An image is a read-only template; a container is a running instance of it",
         "why": "You build an image once and can start many containers from it."},
    ],
    "Git": [
        {"q": "Which command creates a new branch AND switches to it?", "options": ["git checkout -b feature", "git merge feature", "git stash feature", "git commit -b feature"], "answer": "git checkout -b feature",
         "why": "`git checkout -b` (or `git switch -c`) creates and switches in one step."},
    ],
    "REST APIs": [
        {"q": "Which HTTP status code means a resource was successfully created?", "options": ["200", "201", "204", "404"], "answer": "201",
         "why": "201 Created is returned after a successful POST that creates a resource."},
    ],
    "FastAPI": [
        {"q": "Which library does FastAPI use for request data validation?", "options": ["Pydantic", "NumPy", "Requests", "Jinja"], "answer": "Pydantic",
         "why": "FastAPI relies on Pydantic models for validation and automatic documentation."},
    ],
    "Streamlit": [
        {"q": "What happens in Streamlit when a user interacts with a widget?", "options": ["Only that widget refreshes", "The script reruns from top to bottom", "The server restarts", "Nothing until Save is clicked"], "answer": "The script reruns from top to bottom",
         "why": "That is why st.session_state is used to keep values between reruns."},
    ],
    "Pandas": [
        {"q": "What does df.groupby('a')['b'].mean() return?", "options": ["The mean of column b for each value of a", "The mean of column a", "A merged DataFrame", "The row count"], "answer": "The mean of column b for each value of a",
         "why": "groupby splits rows by column a, then mean() aggregates column b within each group."},
    ],
    "NumPy": [
        {"q": "What is the shape of np.zeros((3, 4)).T?", "options": ["(3, 4)", "(4, 3)", "(12,)", "(1, 12)"], "answer": "(4, 3)",
         "why": "Transposing swaps the axes, so 3x4 becomes 4x3."},
    ],
    "Data Structures & Algorithms": [
        {"q": "What is the time complexity of binary search on a sorted array?", "options": ["O(n)", "O(log n)", "O(n log n)", "O(1)"], "answer": "O(log n)",
         "why": "Each step halves the search space."},
        {"q": "Which data structure follows Last-In-First-Out (LIFO)?", "options": ["Queue", "Stack", "Heap", "Graph"], "answer": "Stack",
         "why": "A stack pushes and pops from the same end."},
    ],
    "OOP": [
        {"q": "Which OOP principle is about hiding internal state and exposing only a controlled interface?", "options": ["Inheritance", "Polymorphism", "Encapsulation", "Abstraction of data types"], "answer": "Encapsulation",
         "why": "Encapsulation bundles data with the methods that control access to it."},
    ],
    "Operating Systems": [
        {"q": "Which mechanism is commonly used to prevent race conditions between threads?", "options": ["Mutex / lock", "Compiler flag", "Cache line", "Pipe"], "answer": "Mutex / lock",
         "why": "A mutex ensures only one thread accesses the critical section at a time."},
    ],
    "DBMS": [
        {"q": "Which normal form removes partial dependencies on a composite key?", "options": ["1NF", "2NF", "3NF", "BCNF"], "answer": "2NF",
         "why": "2NF requires every non-key attribute to depend on the whole key, not part of it."},
    ],
    "AWS": [
        {"q": "Which AWS service lets you run code without managing servers?", "options": ["Lambda", "EC2", "RDS", "EBS"], "answer": "Lambda",
         "why": "Lambda is AWS's serverless compute service; you pay per invocation."},
    ],
    "JavaScript": [
        {"q": "Which keyword declares a block-scoped variable that can be reassigned?", "options": ["var", "let", "const", "static"], "answer": "let",
         "why": "let is block-scoped and reassignable; const is block-scoped but not reassignable."},
    ],
    "React": [
        {"q": "Which hook manages local component state?", "options": ["useEffect", "useState", "useRef only", "useServer"], "answer": "useState",
         "why": "useState returns the current value and a setter that triggers a re-render."},
    ],
}

# skills without their own bank borrow questions from a parent topic
MCQ_PARENT = {
    "PostgreSQL": "SQL", "MySQL": "SQL", "SQLite": "SQL", "MongoDB": "DBMS",
    "Keras": "Deep Learning", "TensorFlow": "Deep Learning", "PyTorch": "Deep Learning", "Computer Vision": "Deep Learning",
    "spaCy": "NLP", "Transformers": "NLP", "SentenceTransformers": "NLP", "TF-IDF": "NLP", "LLMs": "NLP",
    "XGBoost": "Machine Learning", "Scikit-learn": "Machine Learning",
    "GitHub": "Git", "GCP": "AWS", "Azure": "AWS", "Flask": "REST APIs", "Django": "REST APIs",
    "Vector Databases": "RAG", "LangChain": "RAG", "CI/CD": "Git",
}


def _bank_for(skill: str) -> tuple[str, list[dict]]:
    topic = skill if skill in MCQ_BANK else MCQ_PARENT.get(skill, "")
    return topic, MCQ_BANK.get(topic, [])


def _llm_mcqs(resume: dict, jd: dict, skills: list[str], n: int) -> list[dict] | None:
    prompt = f"""Create {n} multiple-choice questions to help a student prepare for this role.
Base them on these skills: {', '.join(skills[:10])}. Role: {jd.get('role') or 'not specified'}.
Each question needs 4 plausible options, exactly one correct, and a 1-2 sentence explanation that teaches the concept.
Return ONLY a JSON list with keys: question, options (4 strings), answer (must equal one option), explanation, skill."""
    data = llm_json(prompt)
    if not isinstance(data, list):
        return None
    out = []
    for item in data:
        try:
            opts = [str(o) for o in item["options"]]
            ans = str(item["answer"])
            if len(opts) == 4 and ans in opts:
                out.append({"question": item["question"], "options": opts, "answer": ans,
                            "explanation": item.get("explanation", ""), "skill": item.get("skill", "")})
        except (KeyError, TypeError):
            continue
    return out or None


def generate_mcqs(resume: dict, jd: dict, n: int = 5, use_llm: bool = True, seed: int = 0) -> list[dict]:
    """MCQs focused on the JD's skills the candidate has or should learn."""
    jd_sk = _jd_skills(jd)
    have = set(resume["skills"])
    priority = [s for s in jd_sk if s in have] + [s for s in jd_sk if s not in have] + [s for s in resume["skills"] if s not in jd_sk]
    if use_llm and llm_available():
        got = _llm_mcqs(resume, jd, priority, n)
        if got:
            return got[:n]

    rng = random.Random(seed)
    out: list[dict] = []
    used: set[str] = set()
    for skill in priority:
        topic, items = _bank_for(skill)
        for it in items:
            if it["q"] in used:
                continue
            used.add(it["q"])
            opts = it["options"][:]
            rng.shuffle(opts)
            out.append({"question": it["q"], "options": opts, "answer": it["answer"],
                        "explanation": it["why"], "skill": skill if skill == topic else f"{skill} ({topic})"})
            break  # one question per skill first, so the quiz covers many skills
    if len(out) < n:  # second pass for more questions from the same banks
        for skill in priority:
            topic, items = _bank_for(skill)
            for it in items:
                if it["q"] in used:
                    continue
                used.add(it["q"])
                opts = it["options"][:]
                rng.shuffle(opts)
                out.append({"question": it["q"], "options": opts, "answer": it["answer"],
                            "explanation": it["why"], "skill": skill if skill == topic else f"{skill} ({topic})"})
    return out[:n]
