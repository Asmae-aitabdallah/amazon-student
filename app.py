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
import json
import sqlite3
import uuid
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash

# Optional dependency used by the AI Q&A / role-placement feature further
# down this file. Guarded with try/except so the rest of the app still runs
# (register/login/etc. all work fine) even if `anthropic` isn't installed or
# ANTHROPIC_API_KEY isn't set - the AI features just fall back gracefully.
try:
    import anthropic
except ImportError:  # pragma: no cover - optional dependency
    anthropic = None

# --- App configuration -------------------------------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
app.config["DATABASE"] = os.path.join(app.root_path, "database.db")
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "avatars")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB limit

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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
            avatar        TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL,
            message    TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ai_placements (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER,
            answers_json    TEXT NOT NULL,
            suggested_role  TEXT NOT NULL,
            confidence      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Migration: add avatar column to existing databases that predate this feature.
    try:
        db.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
        db.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
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


# --- Template context --------------------------------------------------------

@app.context_processor
def inject_avatar():
    """Make the current user's avatar filename available in every template."""
    if "user_id" not in session:
        return {"current_avatar": None}
    db = get_db()
    row = db.execute("SELECT avatar FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return {"current_avatar": row["avatar"] if row else None}


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

    # If the person has just been through the AI placement quiz, pre-select
    # the role it suggested for them. They can still change it themselves.
    suggested_role = session.get("suggested_role", "")
    return render_template("register.html", email="", role=suggested_role)


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


# --- AI Q&A / role placement --------------------------------------------------
#
# Two related features, both backed by the Anthropic API:
#
# 1. `/ai-placement` - a short Q&A a new visitor can take BEFORE registering.
#    They answer a few free-text questions, Claude classifies them into one
#    of the site's three account categories (student / educator / parent),
#    and the suggested role is carried over to pre-fill the registration
#    form. Every attempt is logged to the `ai_placements` table.
#
# 2. `/ai-qa` - a simple role-aware Q&A assistant for people who are already
#    logged in. It answers free-text questions with a system prompt tailored
#    to the asker's stored account role, so students, educators and parents
#    each get an answer pitched at them specifically.
#
# Both features require the `anthropic` package (`pip install anthropic`)
# and an ANTHROPIC_API_KEY environment variable. If either is missing, they
# degrade gracefully instead of crashing the app: the placement quiz falls
# back to a small keyword-based classifier, and the Q&A assistant returns a
# friendly "not configured" message.

AI_MODEL = "claude-sonnet-4-6"

# Each question has a stable `id` (used as the form field name / dict key)
# and the text shown to the user. Add/remove questions here freely.
PLACEMENT_QUESTIONS = [
    {
        "id": "q1",
        "text": "What best describes why you're here today?",
    },
    {
        "id": "q2",
        "text": "Who will mainly be using this account - you, your child, or your students/class?",
    },
    {
        "id": "q3",
        "text": "What's the main thing you're hoping to get out of this platform?",
    },
]


def _get_anthropic_client():
    """Return an Anthropic client, or None if the SDK/key isn't available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic is None or not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _keyword_fallback_classifier(answers):
    """
    Very small rule-based backup classifier, used only when the Anthropic
    API isn't configured or the call fails. Keeps the feature usable rather
    than showing an error.
    """
    text = " ".join(answers.values()).lower()
    scores = {"student": 0, "educator": 0, "parent": 0}
    student_words = ["i'm a student", "i am a student", "my course", "my apprenticeship", "myself", "studying", "i want to learn"]
    educator_words = ["teach", "my class", "my students", "school i work", "lecturer", "tutor", "instructor"]
    parent_words = ["my child", "my son", "my daughter", "my kid", "as a parent", "my children"]

    for word in student_words:
        if word in text:
            scores["student"] += 1
    for word in educator_words:
        if word in text:
            scores["educator"] += 1
    for word in parent_words:
        if word in text:
            scores["parent"] += 1

    best_role = max(scores, key=scores.get)
    if scores[best_role] == 0:
        best_role = "student"  # sensible default when nothing matches

    return {
        "role": best_role,
        "confidence": "low",
        "explanation": "Estimated from keywords because the AI service was unavailable.",
    }


def classify_user_role(answers):
    """
    Given a dict of {question_id: answer_text}, ask Claude to classify the
    respondent as 'student', 'educator', or 'parent'.

    Returns a dict: {"role": "...", "confidence": "high|medium|low", "explanation": "..."}
    Falls back to _keyword_fallback_classifier on any failure so the page
    never breaks because of the AI call.
    """
    client = _get_anthropic_client()
    if client is None:
        return _keyword_fallback_classifier(answers)

    qa_text = "\n".join(
        f"- {q['text']} -> {answers.get(q['id'], '').strip()}"
        for q in PLACEMENT_QUESTIONS
    )

    system_prompt = (
        "You are a placement assistant for an education platform with three "
        "account categories: student, educator, and parent. Read the "
        "person's answers below and decide which single category fits them "
        "best. Respond with ONLY a JSON object and nothing else, in exactly "
        'this shape: {"role": "student|educator|parent", "confidence": '
        '"high|medium|low", "explanation": "one short friendly sentence"}.'
    )

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": qa_text}],
        )
        raw = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        # Be forgiving if the model wraps the JSON in a markdown code fence.
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

        data = json.loads(raw)
        role = str(data.get("role", "")).strip().lower()
        if role not in VALID_ROLES:
            raise ValueError(f"Model returned an unrecognised role: {role!r}")

        return {
            "role": role,
            "confidence": str(data.get("confidence", "medium")).strip().lower(),
            "explanation": str(data.get("explanation", "")).strip(),
        }
    except Exception:
        # Any failure (network error, malformed JSON, unexpected shape, the
        # API being down, etc.) - fall back rather than showing a 500 page.
        return _keyword_fallback_classifier(answers)


def answer_role_question(role, question):
    """Ask Claude to answer a user's free-text question, tailored to their account role."""
    client = _get_anthropic_client()
    if client is None:
        return (
            "The AI assistant isn't configured right now (missing "
            "ANTHROPIC_API_KEY). Please try again later or contact support."
        )

    role_context = {
        "student": "a student using an emerging-talent/apprenticeship platform",
        "educator": "an educator or tutor supporting students on this platform",
        "parent": "a parent or guardian supporting their child on this platform",
    }.get(role, "a user of this platform")

    system_prompt = (
        f"You are a helpful assistant embedded in an education platform, "
        f"currently answering a question from {role_context}. Keep answers "
        f"concise, friendly, and appropriate for that audience."
    )

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
    except Exception:
        return "Sorry, the AI assistant couldn't answer that just now. Please try again in a moment."


@app.route("/ai-placement", methods=["GET", "POST"])
def ai_placement():
    """
    A short AI-driven Q&A that helps a new visitor figure out which account
    category (student / educator / parent) fits them, before they register.
    """
    if request.method == "POST":
        answers = {q["id"]: request.form.get(q["id"], "").strip() for q in PLACEMENT_QUESTIONS}

        if not any(answers.values()):
            flash("Please answer at least one question so we can help place you.", "error")
            return render_template("ai_placement.html", questions=PLACEMENT_QUESTIONS, answers=answers, result=None)

        result = classify_user_role(answers)

        # Remember the suggestion for this browser session so the
        # registration form can pre-select it.
        session["suggested_role"] = result["role"]

        db = get_db()
        db.execute(
            "INSERT INTO ai_placements (user_id, answers_json, suggested_role, confidence) "
            "VALUES (?, ?, ?, ?)",
            (
                session.get("user_id"),
                json.dumps(answers),
                result["role"],
                result["confidence"],
            ),
        )
        db.commit()

        return render_template("ai_placement.html", questions=PLACEMENT_QUESTIONS, answers=answers, result=result)

    return render_template("ai_placement.html", questions=PLACEMENT_QUESTIONS, answers={}, result=None)


@app.route("/ai-qa", methods=["GET", "POST"])
@login_required
def ai_qa():
    """
    Role-aware Q&A assistant for logged-in users. Answers are tailored using
    the role already stored on the user's account (student / educator /
    parent), so the same question can get a different answer depending on
    who's asking.
    """
    role = session.get("role", "student")
    answer = None
    question = ""

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if not question:
            flash("Please type a question.", "error")
        else:
            answer = answer_role_question(role, question)

    return render_template("ai_qa.html", role=role, question=question, answer=answer)


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


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        file = request.files.get("avatar")
        if not file or not file.filename:
            flash("No file selected.", "error")
            return redirect(url_for("settings"))
        if not allowed_file(file.filename):
            flash("Only image files are allowed (PNG, JPG, GIF, WebP).", "error")
            return redirect(url_for("settings"))

        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        db = get_db()
        old = db.execute("SELECT avatar FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if old and old["avatar"]:
            old_path = os.path.join(app.config["UPLOAD_FOLDER"], old["avatar"])
            if os.path.exists(old_path):
                os.remove(old_path)

        db.execute("UPDATE users SET avatar = ? WHERE id = ?", (filename, session["user_id"]))
        db.commit()
        flash("Profile picture updated.", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html")


# --- Entry point -------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    # debug=True is for development only. NEVER run debug mode in production:
    # it exposes an interactive debugger that can execute arbitrary code.
    app.run(debug=True, port=5000)
