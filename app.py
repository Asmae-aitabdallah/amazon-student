"""
Amazon Student - Emerging Talent Programs (PROTOTYPE)
=====================================================
A Flask prototype demonstrating registration, role-based content,
accessibility settings, and a feedback form.

SECURITY NOTES (why each choice was made):
- Passwords are hashed with Werkzeug's generate_password_hash (PBKDF2-SHA256
  by default). We never store plaintext passwords.
- All SQL uses parameterised queries (the `?` placeholder), so user input
  cannot be interpreted as SQL. This prevents SQL injection.
- Sessions are signed with SECRET_KEY. In production this MUST come from an
  environment variable, never be hard-coded.
- Inputs are validated server-side. Client-side validation is convenience
  only; it can always be bypassed, so the server is the source of truth.

ACADEMIC / TRADEMARK DISCLAIMER:
This is a student prototype. "Amazon" and "T-Level" branding is used for an
educational exercise only and implies no affiliation with or endorsement by
Amazon.com, Inc. or the UK Department for Education.
"""

import os
import re
import sqlite3
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash

# --- App configuration -------------------------------------------------------

app = Flask(__name__)

# SECRET_KEY signs the session cookie. os.urandom is fine for local dev, but
# it changes on every restart (logging everyone out). In production, set a
# fixed value via the FLASK_SECRET_KEY environment variable.
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
app.config["DATABASE"] = os.path.join(app.root_path, "database.db")

# Hardening the session cookie:
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # JS cannot read the cookie (mitigates XSS theft)
    SESSION_COOKIE_SAMESITE="Lax",  # mitigates CSRF on cross-site navigation
    # SESSION_COOKIE_SECURE=True,   # enable this once you serve over HTTPS
)

VALID_ROLES = {"student", "parent", "educator"}


# --- Database helpers --------------------------------------------------------

def get_db():
    """Open one SQLite connection per request, reusing it within the request."""
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # rows behave like dicts
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close the DB connection at the end of each request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they do not exist. Safe to run repeatedly."""
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL,
            message    TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    db.commit()
    db.close()


# --- Validation --------------------------------------------------------------

# A pragmatic email pattern. Not RFC-perfect (no regex is) but rejects the
# obvious malformed cases without frustrating real users.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration(email, password, role):
    """Return a list of human-readable error strings (empty == valid)."""
    errors = []
    if not email or not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if role not in VALID_ROLES:
        errors.append("Choose a valid role.")
    return errors


# --- Auth decorator ----------------------------------------------------------

def login_required(view):
    """Redirect to login if there is no authenticated user in the session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to view that page.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# --- Routes: public ----------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # .strip() removes accidental leading/trailing whitespace.
        # .lower() on email keeps logins case-insensitive.
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()

        errors = validate_registration(email, password, role)
        if errors:
            for e in errors:
                flash(e, "error")
            # Re-render with the email/role they typed so they don't retype.
            return render_template("register.html", email=email, role=role)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), role),
            )
            db.commit()
        except sqlite3.IntegrityError:
            # UNIQUE constraint on email failed -> already registered.
            flash("An account with that email already exists.", "error")
            return render_template("register.html", email=email, role=role)

        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", email="", role="")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        # Verify the hash. We give the SAME error whether the email is unknown
        # or the password is wrong, so attackers cannot enumerate valid emails.
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.", "error")
            return render_template("login.html", email=email)

        # session.clear() then set values = rotate the session on login,
        # which mitigates session fixation attacks.
        session.clear()
        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["role"] = user["role"]
        flash("Logged in successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html", email="")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        message = request.form.get("message", "").strip()

        errors = []
        if not name:
            errors.append("Please enter your name.")
        if not email or not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        if len(message) < 10:
            errors.append("Message must be at least 10 characters.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("contact.html", name=name, email=email, message=message)

        db = get_db()
        db.execute(
            "INSERT INTO feedback (name, email, message) VALUES (?, ?, ?)",
            (name, email, message),
        )
        db.commit()
        flash("Thanks. Your message has been received.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html", name="", email="", message="")


# --- Routes: authenticated ---------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/info/student")
@login_required
def student_info():
    return render_template("student_info.html")


@app.route("/info/parent")
@login_required
def parent_info():
    return render_template("parent_info.html")


@app.route("/info/educator")
@login_required
def educator_info():
    return render_template("educator_info.html")


@app.route("/settings")
@login_required
def settings():
    # Accessibility preferences are stored client-side (localStorage) so they
    # apply instantly without a round-trip. See static/js/main.js.
    return render_template("settings.html")


# --- Entry point -------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    # debug=True is for development only. NEVER run debug mode in production:
    # it exposes an interactive debugger that can execute arbitrary code.
    app.run(debug=True, port=5000)
