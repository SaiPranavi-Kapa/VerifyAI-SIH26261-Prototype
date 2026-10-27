import os
import re
import json
import time
import hmac
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask, abort, flash, g, redirect, render_template, request,
    send_file, session, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "uploads"
INSTANCE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    DATABASE=os.environ.get("VERIFYAI_DATABASE", str(INSTANCE_DIR / "verifyai.db")),
)
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt"}
ALLOWED_STATUSES = {"Submitted", "Under Review", "Needs Correction", "Approved", "Rejected"}
LOGIN_FAILURES = {}
MAX_LOGIN_FAILURES = 5
LOCK_SECONDS = 60

def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def get_db():
    if "db" not in g:
        db_path = Path(app.config["DATABASE"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(str(db_path), timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','officer','applicant')),
        display_name TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT UNIQUE NOT NULL,
        applicant_id INTEGER NOT NULL REFERENCES users(id),
        title TEXT NOT NULL,
        application_type TEXT NOT NULL,
        status TEXT NOT NULL,
        risk_score INTEGER NOT NULL DEFAULT 0,
        risk_level TEXT NOT NULL DEFAULT 'Low',
        findings_json TEXT NOT NULL DEFAULT '[]',
        extracted_text TEXT NOT NULL DEFAULT '',
        file_name TEXT NOT NULL DEFAULT '',
        stored_name TEXT NOT NULL DEFAULT '',
        file_hash TEXT NOT NULL DEFAULT '',
        review_note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id INTEGER REFERENCES users(id),
        actor_name TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_ref TEXT NOT NULL,
        details TEXT NOT NULL,
        created_at TEXT NOT NULL,
        previous_hash TEXT NOT NULL,
        event_hash TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
    CREATE INDEX IF NOT EXISTS idx_cases_applicant ON cases(applicant_id);
    CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);
    """)
    users = [
        ("demo.admin", "Admin-Demo!84xQ", "admin", "Demo Administrator"),
        ("demo.officer", "Officer-Demo!72pR", "officer", "Demo Compliance Officer"),
        ("demo.applicant", "Applicant-Demo!63mK", "applicant", "Demo Applicant"),
    ]
    for username, password, role, display in users:
        db.execute(
            "INSERT OR IGNORE INTO users(username,password_hash,role,display_name,created_at) VALUES(?,?,?,?,?)",
            (username, generate_password_hash(password), role, display, utcnow())
        )
    db.commit()
    # Seed fictional cases once, so the dashboard is useful at first launch.
    count = db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    if count == 0:
        applicant = db.execute("SELECT id FROM users WHERE username='demo.applicant'").fetchone()["id"]
        samples = [
            ("APP-1042", "Institution registration package", "Institution Registration", "Under Review", 76, "High",
             [{"severity":"high","code":"DATE_MISMATCH","title":"Date fields need review","detail":"The sample record contains inconsistent date values. Confirm against the issuing authority.","recommendation":"Compare the original documents and confirm the correct date."},
              {"severity":"medium","code":"EXPIRY_REVIEW","title":"Expiry requires review","detail":"A sample certificate is marked as near expiry in the demo record.","recommendation":"Request an updated certificate if the expiry is confirmed."}]),
            ("APP-1043", "Faculty credential submission", "Faculty Credential", "Needs Correction", 48, "Medium",
             [{"severity":"medium","code":"MISSING_FIELD","title":"Required field missing","detail":"The sample record is missing a registration/reference field.","recommendation":"Ask the applicant to supply the missing reference."}]),
            ("APP-1044", "Annual compliance return", "Annual Compliance", "Submitted", 12, "Low",
             [{"severity":"low","code":"MANUAL_REVIEW","title":"Routine review recommended","detail":"Automated checks did not identify a high-priority issue. Human review is still required.","recommendation":"Continue with standard officer review."}]),
        ]
        for ref, title, app_type, status, score, level, findings in samples:
            db.execute("""INSERT INTO cases(reference,applicant_id,title,application_type,status,risk_score,risk_level,
                          findings_json,extracted_text,file_name,stored_name,file_hash,review_note,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (ref, applicant, title, app_type, status, score, level, json.dumps(findings),
                        "Fictional seeded demonstration record. No real personal data.", "", "", "", "",
                        utcnow(), utcnow()))
        db.commit()
    db.close()

def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token

app.jinja_env.globals["csrf_token"] = csrf_token

@app.before_request
def security_and_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not sent or not expected or not hmac.compare_digest(sent, expected):
            abort(400, description="Security token missing or expired. Refresh the page and try again.")
    if session.get("user_id"):
        session.permanent = True
        session["last_seen"] = int(time.time())
        # Flask's permanent lifetime also expires the signed session cookie.
    if request.endpoint and request.endpoint not in {"static"}:
        g.request_started = time.time()

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; script-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    return response

def current_user():
    if not session.get("user_id"):
        return None
    if "current_user" not in g:
        g.current_user = get_db().execute(
            "SELECT id,username,role,display_name,active FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()
        if not g.current_user or not g.current_user["active"]:
            session.clear()
            return None
    return g.current_user

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if user["role"] not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def log_event(action, entity_ref, details=""):
    db = get_db()
    actor = current_user()
    actor_id = actor["id"] if actor else None
    actor_name = actor["username"] if actor else "system"
    previous = db.execute("SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1").fetchone()
    previous_hash = previous["event_hash"] if previous else "GENESIS"
    created = utcnow()
    canonical = "|".join([previous_hash, actor_name, action, entity_ref, details, created])
    event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    db.execute("""INSERT INTO audit_events(actor_id,actor_name,action,entity_ref,details,created_at,previous_hash,event_hash)
                  VALUES(?,?,?,?,?,?,?,?)""",
               (actor_id, actor_name, action, entity_ref, details[:500], created, previous_hash, event_hash))
    db.commit()

def verify_audit_chain(rows):
    previous = "GENESIS"
    for row in rows:
        canonical = "|".join([previous, row["actor_name"], row["action"], row["entity_ref"],
                             row["details"], row["created_at"]])
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if row["previous_hash"] != previous or not hmac.compare_digest(expected, row["event_hash"]):
            return False
        previous = row["event_hash"]
    return True

def allowed_case(case):
    user = current_user()
    if not user:
        return False
    return user["role"] in {"admin", "officer"} or case["applicant_id"] == user["id"]

def get_case_or_404(case_id):
    case = get_db().execute("""SELECT c.*, u.display_name AS applicant_name, u.username AS applicant_username
                               FROM cases c JOIN users u ON u.id=c.applicant_id WHERE c.id=?""",
                            (case_id,)).fetchone()
    if not case or not allowed_case(case):
        abort(404)
    return case

def score_findings(findings):
    weights = {"high": 35, "medium": 18, "low": 7}
    score = min(100, sum(weights.get(f.get("severity", "low"), 7) for f in findings))
    level = "High" if score >= 60 else "Medium" if score >= 25 else "Low"
    return score, level

def analyze_text(text, application_type, file_hash, db):
    findings = []
    lowered = text.lower()
    if not text.strip():
        findings.append({"severity":"medium","code":"NO_TEXT","title":"No readable text extracted",
                         "detail":"The file did not yield readable text. OCR may be unavailable or the document may be image-only.",
                         "recommendation":"Use a text-based PDF, install Tesseract for image OCR, or request a readable copy."})
    required = {
        "Institution Registration": ["institution", "registration"],
        "Faculty Credential": ["name", "qualification"],
        "Annual Compliance": ["institution", "year"],
        "General Application": ["name", "date"],
    }.get(application_type, ["name", "date"])
    missing = [field for field in required if field not in lowered]
    if missing:
        findings.append({"severity":"medium","code":"MISSING_FIELD","title":"Expected information not detected",
                         "detail":"The text extractor did not find these expected terms: " + ", ".join(missing) + ". This may be an OCR or document-layout issue, not proof of an omission.",
                         "recommendation":"Review the original document and confirm whether the required information is present."})
    expiry_patterns = re.findall(r"(?:expiry|expires|valid\s+until|validity)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text, flags=re.I)
    if expiry_patterns:
        for date_value in expiry_patterns:
            parsed = None
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%y", "%d-%m-%y"):
                try:
                    parsed = datetime.strptime(date_value, fmt).date()
                    break
                except ValueError:
                    pass
            if parsed:
                days = (parsed - datetime.now().date()).days
                if days < 0:
                    findings.append({"severity":"high","code":"EXPIRED_DATE","title":"Possible expired validity date",
                                     "detail":f"The extracted date {date_value} appears to be in the past.",
                                     "recommendation":"Confirm the date format and issuing authority; request a current document if confirmed."})
                elif days <= 60:
                    findings.append({"severity":"medium","code":"EXPIRY_SOON","title":"Validity date is approaching",
                                     "detail":f"The extracted date {date_value} is within the next 60 days.",
                                     "recommendation":"Confirm the date and plan renewal if applicable."})
    if re.search(r"\b(sample|demo|specimen|not for official use)\b", lowered):
        findings.append({"severity":"low","code":"SAMPLE_MARKER","title":"Sample or specimen marker found",
                         "detail":"The text contains a sample/demo/specimen marker.",
                         "recommendation":"Ensure the file is not a sample when reviewing a real submission."})
    if file_hash:
        prior = db.execute("SELECT reference FROM cases WHERE file_hash=? AND file_hash<>'' LIMIT 1", (file_hash,)).fetchone()
        if prior:
            findings.append({"severity":"medium","code":"DUPLICATE_FILE","title":"Identical file already submitted",
                             "detail":f"The file hash matches an existing submission ({prior['reference']}).",
                             "recommendation":"Check whether the duplicate is an intended resubmission."})
    if not findings:
        findings.append({"severity":"low","code":"RULES_PASSED","title":"No configured rule failures detected",
                         "detail":"The configured text and date checks did not identify a priority issue. This does not prove authenticity.",
                         "recommendation":"Continue with the standard human review process."})
    return findings

def extract_text(path, extension):
    if extension == "txt":
        return path.read_text(encoding="utf-8", errors="ignore")[:100000]
    if extension == "pdf":
        try:
            import fitz
            doc = fitz.open(str(path))
            text = "\n".join(page.get_text("text") for page in doc)
            doc.close()
            return text[:100000]
        except Exception:
            return ""
    if extension in {"png", "jpg", "jpeg"}:
        try:
            from PIL import Image
            import pytesseract
            return pytesseract.image_to_string(Image.open(str(path)))[:100000]
        except Exception:
            return ""
    return ""

@app.route("/")
def index():
    return redirect(url_for("dashboard") if current_user() else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()[:80]
        password = request.form.get("password", "")
        now = time.time()
        record = LOGIN_FAILURES.get(username, {"count": 0, "until": 0})
        if record["until"] > now:
            flash("Too many attempts. Wait a minute before trying again.", "danger")
            return render_template("login.html"), 429
        user = get_db().execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        # Constant-ish work for unknown users helps reduce account-enumeration timing differences.
        valid = check_password_hash(user["password_hash"], password) if user else check_password_hash(
            generate_password_hash("not-the-password"), password)
        if user and valid:
            LOGIN_FAILURES.pop(username, None)
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            session["_csrf_token"] = secrets.token_urlsafe(32)
            log_event("LOGIN_SUCCESS", user["username"], "User signed in")
            return redirect(url_for("dashboard"))
        record["count"] += 1
        if record["count"] >= MAX_LOGIN_FAILURES:
            record = {"count": 0, "until": now + LOCK_SECONDS}
        LOGIN_FAILURES[username] = record
        log_event("LOGIN_FAILURE", username or "unknown", "Failed sign-in attempt")
        flash("Sign-in failed. Check your credentials and try again.", "danger")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    user = current_user()
    log_event("LOGOUT", user["username"], "User signed out")
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = current_user()
    if user["role"] == "applicant":
        rows = db.execute("""SELECT c.*, u.display_name AS applicant_name FROM cases c JOIN users u ON u.id=c.applicant_id
                             WHERE c.applicant_id=? ORDER BY c.updated_at DESC""", (user["id"],)).fetchall()
    else:
        rows = db.execute("""SELECT c.*, u.display_name AS applicant_name FROM cases c JOIN users u ON u.id=c.applicant_id
                             ORDER BY CASE c.risk_level WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
                             c.updated_at DESC""").fetchall()
    counts = {
        "total": len(rows),
        "flagged": sum(1 for r in rows if r["risk_level"] == "High"),
        "pending": sum(1 for r in rows if r["status"] in {"Submitted", "Under Review", "Needs Correction"}),
        "approved": sum(1 for r in rows if r["status"] == "Approved"),
    }
    recent_events = []
    if user["role"] in {"admin", "officer"}:
        recent_events = db.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", cases=rows, counts=counts, recent_events=recent_events)

@app.route("/cases/new", methods=["GET", "POST"])
@login_required
def new_case():
    user = current_user()
    if request.method == "POST":
        title = request.form.get("title", "").strip()[:120]
        app_type = request.form.get("application_type", "General Application")
        allowed_types = {"Institution Registration", "Faculty Credential", "Annual Compliance", "General Application"}
        if not title or app_type not in allowed_types:
            flash("Enter a title and select a valid application type.", "danger")
            return render_template("new_case.html")
        upload = request.files.get("document")
        if not upload or not upload.filename:
            flash("Choose a document to upload.", "warning")
            return render_template("new_case.html")
        original_name = secure_filename(upload.filename)
        ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
        if ext not in ALLOWED_EXTENSIONS:
            flash("Unsupported file type. Upload PDF, PNG, JPG, JPEG, or TXT.", "danger")
            return render_template("new_case.html")
        content = upload.read()
        if not content:
            flash("The selected file is empty.", "danger")
            return render_template("new_case.html")
        if len(content) > app.config["MAX_CONTENT_LENGTH"]:
            flash("The file is too large. Maximum size is 12 MB.", "danger")
            return render_template("new_case.html")
        file_hash = hashlib.sha256(content).hexdigest()
        ref = "VAI-" + secrets.token_hex(3).upper()
        stored_name = ref + "_" + secrets.token_hex(8) + "." + ext
        stored_path = UPLOAD_DIR / stored_name
        stored_path.write_bytes(content)
        extracted = extract_text(stored_path, ext)
        db = get_db()
        findings = analyze_text(extracted, app_type, file_hash, db)
        score, level = score_findings(findings)
        status = "Submitted"
        if level == "High":
            status = "Under Review"
        cursor = db.execute("""INSERT INTO cases(reference,applicant_id,title,application_type,status,risk_score,risk_level,
                            findings_json,extracted_text,file_name,stored_name,file_hash,review_note,created_at,updated_at)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (ref, user["id"], title, app_type, status, score, level, json.dumps(findings),
                             extracted[:100000], original_name[:200], stored_name, file_hash, "", utcnow(), utcnow()))
        db.commit()
        log_event("CASE_CREATED", ref, f"Application created; risk level {level}; score {score}")
        log_event("DOCUMENT_UPLOADED", ref, f"Uploaded file SHA-256 {file_hash[:16]}…")
        flash(f"Application {ref} created and checked.", "success")
        return redirect(url_for("case_detail", case_id=cursor.lastrowid))
    return render_template("new_case.html")

@app.route("/cases/<int:case_id>")
@login_required
def case_detail(case_id):
    case = get_case_or_404(case_id)
    findings = json.loads(case["findings_json"] or "[]")
    return render_template("case_detail.html", case=case, findings=findings)

@app.route("/cases/<int:case_id>/review", methods=["POST"])
@roles_required("admin", "officer")
def review_case(case_id):
    case = get_case_or_404(case_id)
    status = request.form.get("status", "")
    note = request.form.get("review_note", "").strip()[:1000]
    if status not in ALLOWED_STATUSES:
        abort(400, description="Invalid case status.")
    db = get_db()
    db.execute("UPDATE cases SET status=?, review_note=?, updated_at=? WHERE id=?",
               (status, note, utcnow(), case_id))
    db.commit()
    log_event("CASE_REVIEWED", case["reference"], f"Status set to {status}; note length {len(note)}")
    flash("Review decision saved.", "success")
    return redirect(url_for("case_detail", case_id=case_id))

@app.route("/cases/<int:case_id>/simulate", methods=["POST"])
@login_required
def simulate_case(case_id):
    case = get_case_or_404(case_id)
    findings = json.loads(case["findings_json"] or "[]")
    resolved_codes = set(request.form.getlist("resolve"))
    remaining = [f for f in findings if f.get("code") not in resolved_codes]
    score, level = score_findings(remaining)
    log_event("WHAT_IF_SIMULATION", case["reference"], f"Resolved codes: {','.join(sorted(resolved_codes)) or 'none'}")
    return render_template("case_detail.html", case=case, findings=findings,
                           simulation={"score": score, "level": level, "remaining": remaining,
                                       "resolved": sorted(resolved_codes)})

@app.route("/cases/<int:case_id>/report")
@login_required
def report_case(case_id):
    case = get_case_or_404(case_id)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from io import BytesIO
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                                topMargin=18*mm, bottomMargin=18*mm)
        styles = getSampleStyleSheet()
        story = [Paragraph("VerifyAI — Compliance Review Report", styles["Title"]),
                 Paragraph("Prototype report • Not an official certificate of authenticity", styles["Italic"]),
                 Spacer(1, 10)]
        rows = [["Reference", case["reference"]], ["Application", case["title"]],
                ["Type", case["application_type"]], ["Status", case["status"]],
                ["Risk score", f'{case["risk_score"]}/100 ({case["risk_level"]})'],
                ["Submitted", case["created_at"]], ["Applicant", case["applicant_name"]]]
        table = Table(rows, colWidths=[38*mm, 120*mm])
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#e9eef7")),
                                   ("GRID",(0,0),(-1,-1),0.4,colors.grey),
                                   ("VALIGN",(0,0),(-1,-1),"TOP"),
                                   ("LEFTPADDING",(0,0),(-1,-1),7),
                                   ("RIGHTPADDING",(0,0),(-1,-1),7),
                                   ("TOPPADDING",(0,0),(-1,-1),6),
                                   ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story += [table, Spacer(1, 12), Paragraph("Findings and recommended actions", styles["Heading2"])]
        for item in json.loads(case["findings_json"] or "[]"):
            story.append(Paragraph(f'<b>{item.get("severity","").upper()}: {item.get("title","")}</b>', styles["BodyText"]))
            story.append(Paragraph(item.get("detail","").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"), styles["BodyText"]))
            story.append(Paragraph("Action: " + item.get("recommendation","").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"), styles["BodyText"]))
            story.append(Spacer(1, 5))
        if case["review_note"]:
            story += [Paragraph("Officer review note", styles["Heading2"]),
                      Paragraph(case["review_note"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"), styles["BodyText"])]
        story += [Spacer(1, 12), Paragraph("Automated checks can be wrong or incomplete. Human review and official verification remain necessary.", styles["Italic"])]
        doc.build(story)
        buffer.seek(0)
        log_event("REPORT_DOWNLOADED", case["reference"], "PDF report generated")
        return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                         download_name=f"VerifyAI_{case['reference']}_report.pdf")
    except ImportError:
        flash("PDF report dependency is missing. Run pip install -r requirements.txt.", "danger")
        return redirect(url_for("case_detail", case_id=case_id))

@app.route("/files/<int:case_id>")
@login_required
def protected_file(case_id):
    case = get_case_or_404(case_id)
    if not case["stored_name"]:
        abort(404)
    path = UPLOAD_DIR / case["stored_name"]
    if not path.exists():
        abort(404)
    log_event("DOCUMENT_VIEWED", case["reference"], "Authorized document view/download")
    return send_file(path, as_attachment=True, download_name=case["file_name"] or "document")

@app.route("/audit")
@roles_required("admin", "officer")
def audit():
    db = get_db()
    all_rows = db.execute("SELECT * FROM audit_events ORDER BY id ASC").fetchall()
    valid = verify_audit_chain(all_rows)
    rows = list(reversed(all_rows[-250:]))
    return render_template("audit.html", events=rows, chain_valid=valid)

@app.route("/api/health")
def health():
    return {"status": "ok", "service": "VerifyAI prototype", "mode": "demo"}, 200

@app.errorhandler(403)
def forbidden(_error):
    return render_template("base_error.html", code=403, message="Your role does not have permission to access this page."), 403

@app.errorhandler(404)
def not_found(_error):
    return render_template("base_error.html", code=404, message="This resource is unavailable or you do not have permission to view it."), 404

@app.errorhandler(400)
def bad_request(error):
    return render_template("base_error.html", code=400, message=getattr(error, "description", "The request could not be processed.")), 400

@app.errorhandler(413)
def too_large(_error):
    return render_template("base_error.html", code=413, message="The uploaded file exceeds the 12 MB limit."), 413

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
