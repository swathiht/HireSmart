from app.core.skills import extract_skills, group_by_category


def test_alias_matching_variants():
    found = extract_skills("Used sklearn, JS and Postgres with k8s and HuggingFace")
    assert {"Scikit-learn", "JavaScript", "PostgreSQL", "Kubernetes", "Transformers"} <= set(found)


def test_no_false_positive_inside_words():
    assert "Java" not in extract_skills("I love javascript only")      # JavaScript, not Java
    assert "R" not in extract_skills("Strong research and reporting")   # 'R' must not match inside words
    assert "C" not in extract_skills("Collaborated with the team")


def test_cpp_and_c_sharp_symbols():
    assert "C++" in extract_skills("Languages: Python, C++, SQL")


def test_group_by_category():
    groups = group_by_category(["Python", "Docker", "Pandas"])
    assert groups["Languages"] == ["Python"] and groups["Tools"] == ["Docker"] and groups["Data"] == ["Pandas"]
