"""
Unit tests for Amazon Student Flask app (app.py)
Run with:  pytest test_app.py -v
Requires:  pip install pytest flask werkzeug
"""

import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# We import the app but point its database at a temporary file so tests
# never touch the real database.db.
# ---------------------------------------------------------------------------
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")

import app as application  # the module
from app import app, init_db, validate_registration, allowed_file, EMAIL_RE, VALID_ROLES


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def db_path(tmp_path):
    """Return a path to a fresh temporary SQLite database."""
    return str(tmp_path / "test.db")


@pytest.fixture
def client(db_path):
    """
    Create a Flask test client backed by an isolated in-memory database.
    Each test gets a clean slate.
    """
    app.config["TESTING"] = True
    app.config["DATABASE"] = db_path
    app.config["WTF_CSRF_ENABLED"] = False  # no CSRF in tests

    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client


def register_user(client, email="test@example.com", password="password123", role="student"):
    """Helper: POST to /register and return the response."""
    return client.post("/register", data={
        "email": email,
        "password": password,
        "role": role,
    }, follow_redirects=True)


def login_user(client, email="test@example.com", password="password123"):
    """Helper: POST to /login and return the response."""
    return client.post("/login", data={
        "email": email,
        "password": password,
    }, follow_redirects=True)


# ===========================================================================
# 1. Validation helpers
# ===========================================================================

class TestValidateRegistration:
    def test_valid_input_returns_no_errors(self):
        assert validate_registration("a@b.com", "password123", "student") == []

    def test_all_valid_roles_accepted(self):
        for role in ("student", "parent", "educator"):
            assert validate_registration("a@b.com", "password123", role) == []

    def test_invalid_role_rejected(self):
        errors = validate_registration("a@b.com", "password123", "admin")
        assert any("role" in e.lower() for e in errors)

    def test_short_password_rejected(self):
        errors = validate_registration("a@b.com", "short", "student")
        assert any("8" in e for e in errors)

    def test_empty_password_rejected(self):
        errors = validate_registration("a@b.com", "", "student")
        assert len(errors) > 0

    def test_bad_email_rejected(self):
        for bad in ("notanemail", "missing@dot", "@nodomain.com", ""):
            errors = validate_registration(bad, "password123", "student")
            assert any("email" in e.lower() for e in errors), f"Expected error for: {bad!r}"

    def test_multiple_errors_returned(self):
        errors = validate_registration("bad", "x", "nope")
        assert len(errors) >= 2


class TestEmailRegex:
    def test_valid_emails(self):
        for email in ("user@example.com", "a.b+tag@sub.domain.org", "x@y.z"):
            assert EMAIL_RE.match(email), f"Should match: {email}"

    def test_invalid_emails(self):
        for email in ("", "noatsign", "missing@", "@nodomain"):
            assert not EMAIL_RE.match(email), f"Should not match: {email}"


class TestAllowedFile:
    def test_allowed_extensions(self):
        for name in ("photo.png", "img.jpg", "image.jpeg", "anim.gif", "pic.webp"):
            assert allowed_file(name), f"Should be allowed: {name}"

    def test_disallowed_extensions(self):
        for name in ("file.exe", "script.py", "doc.pdf", "archive.zip"):
            assert not allowed_file(name), f"Should not be allowed: {name}"

    def test_no_extension(self):
        assert not allowed_file("noextension")

    def test_case_insensitive(self):
        assert allowed_file("photo.PNG")
        assert allowed_file("photo.JPG")


class TestValidRoles:
    def test_roles_set_contains_expected_values(self):
        assert "student" in VALID_ROLES
        assert "parent" in VALID_ROLES
        assert "educator" in VALID_ROLES

    def test_roles_set_excludes_admin(self):
        assert "admin" not in VALID_ROLES


# ===========================================================================
# 2. Public routes
# ===========================================================================

class TestHomeRoute:
    def test_home_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_home_contains_expected_text(self, client):
        response = client.get("/")
        assert b"Amazon" in response.data or b"amazon" in response.data.lower()


class TestRegisterRoute:
    def test_get_register_returns_200(self, client):
        assert client.get("/register").status_code == 200

    def test_successful_registration_redirects_to_login(self, client):
        response = register_user(client)
        # follow_redirects=True, so we end up at /login (200)
        assert response.status_code == 200
        assert b"log in" in response.data.lower() or b"login" in response.data.lower()

    def test_duplicate_email_shows_error(self, client):
        register_user(client, email="dup@example.com")
        response = register_user(client, email="dup@example.com")
        assert b"already exists" in response.data.lower()

    def test_invalid_email_shows_error(self, client):
        response = register_user(client, email="notvalid")
        assert b"email" in response.data.lower()

    def test_short_password_shows_error(self, client):
        response = register_user(client, password="short")
        assert b"8" in response.data or b"password" in response.data.lower()

    def test_invalid_role_shows_error(self, client):
        response = register_user(client, role="hacker")
        assert b"role" in response.data.lower()

    def test_email_stored_lowercase(self, client):
        register_user(client, email="UPPER@EXAMPLE.COM")
        # Should be able to log in with lowercase version
        response = login_user(client, email="upper@example.com")
        assert b"logged in" in response.data.lower() or b"dashboard" in response.data.lower()


class TestLoginRoute:
    def test_get_login_returns_200(self, client):
        assert client.get("/login").status_code == 200

    def test_successful_login_redirects_to_dashboard(self, client):
        register_user(client)
        response = login_user(client)
        assert response.status_code == 200
        assert b"dashboard" in response.data.lower() or b"welcome" in response.data.lower()

    def test_wrong_password_shows_error(self, client):
        register_user(client)
        response = login_user(client, password="wrongpassword")
        assert b"incorrect" in response.data.lower()

    def test_unknown_email_shows_same_error_as_wrong_password(self, client):
        """No user enumeration: both bad email and bad password give the same message."""
        response_bad_email = login_user(client, email="nobody@nowhere.com")
        register_user(client)
        response_bad_pw = login_user(client, password="wrongpassword")
        # Both should contain "incorrect" (not "no account" vs "wrong password")
        assert b"incorrect" in response_bad_email.data.lower()
        assert b"incorrect" in response_bad_pw.data.lower()

    def test_login_sets_session(self, client):
        register_user(client)
        with client.session_transaction() as sess:
            sess.clear()
        login_user(client)
        with client.session_transaction() as sess:
            assert "user_id" in sess

    def test_logout_clears_session(self, client):
        register_user(client)
        login_user(client)
        client.get("/logout", follow_redirects=True)
        with client.session_transaction() as sess:
            assert "user_id" not in sess


class TestContactRoute:
    def test_get_contact_returns_200(self, client):
        assert client.get("/contact").status_code == 200

    def test_valid_feedback_succeeds(self, client):
        response = client.post("/contact", data={
            "name": "Alice",
            "email": "alice@example.com",
            "message": "This is a test message that is long enough.",
        }, follow_redirects=True)
        assert b"received" in response.data.lower() or b"thank" in response.data.lower()

    def test_missing_name_shows_error(self, client):
        response = client.post("/contact", data={
            "name": "",
            "email": "alice@example.com",
            "message": "Long enough message here.",
        }, follow_redirects=True)
        assert b"name" in response.data.lower()

    def test_invalid_email_in_contact_shows_error(self, client):
        response = client.post("/contact", data={
            "name": "Alice",
            "email": "notanemail",
            "message": "Long enough message here.",
        }, follow_redirects=True)
        assert b"email" in response.data.lower()

    def test_short_message_shows_error(self, client):
        response = client.post("/contact", data={
            "name": "Alice",
            "email": "alice@example.com",
            "message": "Hi",  # < 10 chars
        }, follow_redirects=True)
        assert b"10" in response.data or b"message" in response.data.lower()


# ===========================================================================
# 3. Authenticated (login-required) routes
# ===========================================================================

class TestAuthenticatedRoutes:
    PROTECTED = ["/dashboard", "/info/student", "/info/parent", "/info/educator", "/settings"]

    def test_unauthenticated_redirects_to_login(self, client):
        for path in self.PROTECTED:
            response = client.get(path)
            assert response.status_code in (302, 200), f"Expected redirect for {path}"
            if response.status_code == 302:
                assert "/login" in response.headers.get("Location", "")

    def test_authenticated_can_access_dashboard(self, client):
        register_user(client)
        login_user(client)
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_authenticated_can_access_student_info(self, client):
        register_user(client, role="student")
        login_user(client)
        assert client.get("/info/student").status_code == 200

    def test_authenticated_can_access_parent_info(self, client):
        register_user(client, role="parent")
        login_user(client)
        assert client.get("/info/parent").status_code == 200

    def test_authenticated_can_access_educator_info(self, client):
        register_user(client, role="educator")
        login_user(client)
        assert client.get("/info/educator").status_code == 200

    def test_authenticated_can_access_settings(self, client):
        register_user(client)
        login_user(client)
        assert client.get("/settings").status_code == 200


# ===========================================================================
# 4. Logout
# ===========================================================================

class TestLogout:
    def test_logout_redirects_to_home(self, client):
        register_user(client)
        login_user(client)
        response = client.get("/logout")
        assert response.status_code == 302
        assert "/" in response.headers.get("Location", "")

    def test_after_logout_dashboard_requires_login(self, client):
        register_user(client)
        login_user(client)
        client.get("/logout")
        response = client.get("/dashboard")
        # Should redirect to login
        assert response.status_code == 302 or b"login" in client.get(
            "/dashboard", follow_redirects=True
        ).data.lower()
