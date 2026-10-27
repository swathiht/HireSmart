import pytest

from app.auth.auth import AuthError, create_token, login, register, require_role, verify_token


def test_register_login_roles():
    u = register("A@Example.com", "Ann", "password123", "student")
    assert u["email"] == "a@example.com"
    assert login("a@example.com", "password123")["role"] == "student"
    with pytest.raises(AuthError):
        login("a@example.com", "wrong-password")
    with pytest.raises(AuthError):
        login("nobody@example.com", "password123")


def test_registration_validation():
    with pytest.raises(AuthError):
        register("bad-email", "X", "password123", "student")
    with pytest.raises(AuthError):
        register("x@example.com", "X", "short", "student")
    with pytest.raises(AuthError):
        register("x@example.com", "X", "password123", "admin")
    register("x@example.com", "X", "password123", "recruiter")
    with pytest.raises(AuthError):
        register("x@example.com", "X", "password123", "recruiter")


def test_role_guard_and_token():
    s = register("s@example.com", "S", "password123", "student")
    with pytest.raises(AuthError):
        require_role(s, "recruiter")
    assert require_role(s, "student") is s
    tok = create_token(s)
    assert verify_token(tok)["role"] == "student"
    with pytest.raises(AuthError):
        verify_token(tok[:-2] + "xx")
    with pytest.raises(AuthError):
        verify_token(create_token(s, ttl_seconds=-5))


def test_password_is_not_stored_in_plain_text():
    from app.db.database import connect
    register("p@example.com", "P", "password123", "student")
    with connect() as c:
        row = c.execute("SELECT password_hash, salt FROM users").fetchone()
    assert "password123" not in row["password_hash"] and len(row["salt"]) == 32
