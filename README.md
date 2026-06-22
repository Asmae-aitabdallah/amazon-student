# Amazon Student — Emerging Talent Programs (prototype)

A functional web prototype: users register, log in, pick a role
(student / parent / educator), and see T-Level information tailored to that
role. Includes accessibility settings (dark mode, larger text, high contrast)
and a contact/feedback form.

> **Academic / trademark disclaimer**
> This is a student prototype built for an educational exercise. The "Amazon"
> name and styling are used only to resemble the brief. It is **not** affiliated
> with or endorsed by Amazon. Do not deploy publicly or present it as a real
> Amazon product.

## Tech stack
- **Front end:** HTML, CSS, vanilla JavaScript
- **Back end:** Python + Flask
- **Database:** SQLite (created automatically on first run)

## Folder structure
```
amazon_student/
├── app.py                  # Flask app: routes, auth, validation, DB setup
├── requirements.txt        # Python dependencies
├── database.db             # SQLite DB (auto-created; git-ignored)
├── README.md
├── ASSETS_LOG.md           # Sources for code + content
├── .gitignore
├── static/
│   ├── css/
│   │   └── style.css       # All styling + theming (dark/contrast/large text)
│   └── js/
│       └── main.js         # Accessibility toggles, saved in localStorage
└── templates/
    ├── base.html           # Shared layout every page extends
    ├── home.html           # 1. Home
    ├── register.html       # 2. Register
    ├── login.html          # 3. Login
    ├── dashboard.html      # 4. Dashboard (routes by role)
    ├── student_info.html   # 5. Student information
    ├── parent_info.html    # 6. Parent information
    ├── educator_info.html  # 7. Educator information
    ├── settings.html       # 8. Settings (accessibility)
    └── contact.html        # 9. Contact us
```

## Run it locally
You need Python 3.9+.

```bash
# 1. Go into the project folder
cd amazon_student

# 2. (Recommended) create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows (PowerShell)

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Recommended) set a fixed secret key so sessions survive restarts
export FLASK_SECRET_KEY="change-this-to-a-long-random-string"   # macOS/Linux
# setx FLASK_SECRET_KEY "change-this-..."                       # Windows

# 5. Run
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

The database (`database.db`) is created automatically the first time you run
the app. Register an account, then log in.

## Security practices used (and why)
- **Password hashing** — passwords are stored as PBKDF2-SHA256 hashes via
  Werkzeug's `generate_password_hash`. Plaintext is never stored.
- **SQL injection prevention** — every query uses parameterised statements
  (`?` placeholders), so user input can never be executed as SQL.
- **Session security** — the session cookie is signed with `SECRET_KEY`, marked
  `HttpOnly` (JS can't read it) and `SameSite=Lax` (basic CSRF mitigation). The
  session is rotated on login to prevent session fixation.
- **Input validation** — all form input is validated server-side (email format,
  password length, role whitelist, message length). Client-side HTML attributes
  are convenience only.
- **No user enumeration** — login returns the same error whether the email is
  unknown or the password is wrong.

## Known limitations (honest list)
These are deliberately out of scope for a prototype but would matter in production:
- **No CSRF tokens on forms.** `SameSite=Lax` helps, but a real app should use
  Flask-WTF's CSRF protection on every POST.
- **No rate limiting / lockout** on login, so brute-force attempts aren't slowed.
- **No email verification** or password reset flow.
- **Accessibility prefs are per-device** (localStorage), not tied to the account.
- **`debug=True`** is set for development convenience — never run that in production.
- **Output escaping:** Jinja2 auto-escapes by default (good), but if you ever
  mark content `|safe`, validate it first to avoid XSS.
