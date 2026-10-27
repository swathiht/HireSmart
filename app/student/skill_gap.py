"""Skill-gap analysis: which JD skills are missing, how important they are, and how to learn them."""
from __future__ import annotations

from ..core.skills import category_of, related_skills

# skill -> (what to learn, mini-project idea). Resource names only (no links that could go stale).
LEARN: dict[str, tuple[str, str]] = {
    "Docker": ("Images, containers, Dockerfile, docker-compose, volumes", "Containerise one of your Streamlit/FastAPI apps and run it with docker-compose."),
    "Kubernetes": ("Pods, deployments, services; start with minikube/kind", "Deploy a containerised app to a local kind cluster."),
    "AWS": ("IAM, S3, Lambda, EC2 basics; set a billing alert first", "Build an S3-triggered Lambda that parses an uploaded file."),
    "GCP": ("Cloud Run, Cloud Storage, IAM", "Deploy a container to Cloud Run."),
    "Azure": ("App Service, Blob Storage, Functions", "Host a small API on Azure for Students credits."),
    "CI/CD": ("GitHub Actions workflows, secrets, caching", "Add a workflow that runs pytest and builds a Docker image on every push."),
    "REST APIs": ("HTTP methods, status codes, JSON, authentication, API design", "Build a CRUD API with FastAPI and document it with the /docs page."),
    "FastAPI": ("Routes, Pydantic models, dependency injection, auth", "Expose your scoring logic as a documented REST API."),
    "Flask": ("Routing, templates, blueprints", "Build a small CRUD app with SQLite."),
    "SQL": ("SELECT, JOINs, GROUP BY, window functions, indexes", "Design a 4-table schema and write 10 analytical queries."),
    "PostgreSQL": ("Schemas, indexes, transactions, psycopg / SQLAlchemy", "Move a SQLite project to PostgreSQL."),
    "MongoDB": ("Documents, collections, aggregation pipeline", "Store parsed resumes as JSON documents."),
    "PyTorch": ("Tensors, autograd, nn.Module, training loop", "Re-implement an existing Keras model in PyTorch."),
    "TensorFlow": ("Keras API, tf.data, callbacks, saving models", "Train an image classifier with transfer learning."),
    "Computer Vision": ("CNNs, augmentation, transfer learning, OpenCV", "Build a small image classifier with a pre-trained ResNet."),
    "NLP": ("Tokenisation, TF-IDF, embeddings, transformers", "Build a text classifier and compare TF-IDF vs embeddings."),
    "LLMs": ("Prompting, API usage, evaluation, guard-rails", "Create a small tool that summarises job descriptions."),
    "RAG": ("Chunking, embeddings, vector stores, retrieval evaluation", "Build a question-answering bot over a few PDFs."),
    "LangChain": ("Chains, retrievers, tools, agents", "Rebuild a simple RAG pipeline with LangChain."),
    "Vector Databases": ("FAISS / Chroma / pgvector, ANN indexes", "Index 1,000 document chunks and measure recall@k."),
    "Machine Learning": ("Supervised learning, validation, metrics, feature engineering", "Do an end-to-end Kaggle-style project with a proper baseline."),
    "Deep Learning": ("Backprop, CNNs/RNNs, regularisation, optimisers", "Train a CNN and plot learning curves."),
    "Scikit-learn": ("Pipelines, cross-validation, grid search", "Wrap preprocessing and a model in one Pipeline."),
    "Pandas": ("Indexing, groupby, merge, cleaning", "Clean a messy CSV and publish a short EDA notebook."),
    "Data Visualization": ("Matplotlib/Plotly, choosing the right chart", "Build an interactive dashboard from a public dataset."),
    "Power BI": ("Data model, DAX basics, dashboards", "Recreate a sales dashboard from a sample dataset."),
    "Tableau": ("Calculated fields, dashboards, storytelling", "Publish a dashboard from a public dataset."),
    "Git": ("Branches, merge vs rebase, pull requests", "Contribute a small PR to an open-source repo."),
    "Linux": ("Shell, permissions, processes, ssh", "Set up a small server and deploy an app by hand."),
    "React": ("Components, hooks, state, fetching APIs", "Build a front end for one of your APIs."),
    "JavaScript": ("ES6, async/await, DOM, fetch", "Add interactivity to a static page."),
    "Software Testing": ("pytest, fixtures, mocking, coverage", "Add tests with 70%+ coverage to a project."),
    "Statistics": ("Distributions, hypothesis tests, confidence intervals", "Run an A/B-test analysis on sample data."),
    "Data Structures & Algorithms": ("Arrays, hash maps, trees, graphs, complexity", "Solve a few problems per week and explain each solution aloud."),
}


def _learn_for(skill: str) -> tuple[str, str]:
    if skill in LEARN:
        return LEARN[skill]
    return (f"Official {skill} documentation and a beginner tutorial", f"Build a small project that uses {skill} and add it to your resume.")


def gap_report(resume: dict, jd: dict) -> dict:
    have = set(resume["skills"])
    weights = jd.get("skill_weights", {})
    gaps = []
    for kind, skills in (("required", jd.get("required_skills", [])), ("preferred", jd.get("preferred_skills", []))):
        for s in skills:
            if s in have:
                continue
            learn, project = _learn_for(s)
            near = [r for r in related_skills(s) if r in have][:3]
            importance = (10 if kind == "required" else 5) + min(5, weights.get(s, 1))
            gaps.append({
                "skill": s, "category": category_of(s), "type": kind, "importance": importance,
                "you_already_have": near, "what_to_learn": learn, "mini_project": project,
            })
    gaps.sort(key=lambda g: -g["importance"])
    matched = [s for s in jd.get("required_skills", []) + jd.get("preferred_skills", []) if s in have]
    total = len(jd.get("required_skills", [])) + len(jd.get("preferred_skills", []))
    return {"gaps": gaps, "matched": matched, "coverage": round(len(matched) / total * 100, 1) if total else 0.0}
