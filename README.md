# VerifyAI — SIH Functional Prototype

**AI-assisted application validation, document checks, and regulatory compliance review.**

VerifyAI is a demonstrator for SIH problem statement **SIH26261**. It includes a Flask backend, SQLite persistence, role-based access, document uploads, text extraction, rule-based validation, explainable risk scoring, a review queue, audit events, a what-if simulator, an evidence-grounded helper, and PDF reports.

> **Important:** This is a prototype, not an official AICTE service. It does not connect to government databases and cannot conclusively authenticate a document. Use synthetic demo data only. Risk scores are triage aids, not automatic decisions.

## Features

- Distinctive dark “mission control” dashboard with responsive layout.
- Demo login roles: Administrator, Compliance Officer, Applicant.
- Server-side role checks and applicant ownership checks.
- Password hashing with Werkzeug, login throttling, CSRF tokens, session expiry, and security headers.
- PDF text extraction via PyMuPDF; image OCR via Tesseract when the Tesseract binary is installed.
- Document type, expiry, required-field, keyword, and duplicate-hash checks.
- Explainable 0–100 risk score with finding-level reasons and recommendations.
- Case status workflow: Submitted, Under Review, Needs Correction, Approved, Rejected.
- What-if simulator to test how resolving findings affects the score.
- Evidence-grounded “Ask VerifyAI” helper based on the actual findings.
- Hash-chained audit events for tamper-evidence.
- Downloadable PDF review reports.
- Seeded fictional demo cases and users.

## Demo credentials

These are **development-only** credentials. Change them before any public deployment.

| Role | Username | Password |
|---|---|---|
| Administrator | `demo.admin` | `Admin-Demo!84xQ` |
| Compliance Officer | `demo.officer` | `Officer-Demo!72pR` |
| Applicant | `demo.applicant` | `Applicant-Demo!63mK` |

All seeded records and documents are fictional.

## Run locally (Windows)

1. Install Python 3.10 or newer.
2. Extract the ZIP.
3. Open a terminal in the extracted `VerifyAI_SIH_Prototype` folder.
4. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

5. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

6. Set a secret key for local development (optional; the app generates a temporary key if omitted):

   ```powershell
   $env:FLASK_SECRET_KEY = "replace-with-a-long-random-secret"
   ```

7. Start the application:

   ```powershell
   python app.py
   ```

8. Open `http://127.0.0.1:5000`.

The SQLite database is created automatically at `instance/verifyai.db`. Uploaded files are stored in the private `uploads/` folder and are served only through authenticated routes.

### OCR note
PDF text extraction works with text-based PDFs. Image OCR requires the Tesseract OCR engine installed on the computer and available on PATH. If Tesseract is missing, the app explains that image OCR is unavailable and still lets the officer enter a review note. For a reliable live demo, use text-based PDFs or install Tesseract.

## Deploy to Render

1. Push the extracted project to a GitHub repository.
2. Create a **Web Service** on Render and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variable `FLASK_SECRET_KEY` with a long random value.
6. Use a persistent disk for the SQLite database and uploads, or configure a persistent PostgreSQL/database and private object storage before handling real records.
7. Use HTTPS and change/remove demo credentials before public access.

**Do not use the included demo credentials for a public service.** The prototype seeds them on first database initialization. For a public demo, replace the credentials and seed data before deployment.

## Security scope and limitations

This prototype demonstrates security controls but is not production-certified. Before real confidential data is processed, obtain a security review and implement production-grade account provisioning, MFA, backup/restore tests, malware scanning, retention/deletion controls, encryption/key management, monitoring, and a properly managed persistent database/object store. Hash-chained audit records are tamper-evident, not impossible to alter if an attacker controls the database and application.

## Project structure

```text
VerifyAI_SIH_Prototype/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── new_case.html
│   ├── case_detail.html
│   └── audit.html
├── static/
│   ├── css/style.css
│   └── js/app.js
├── uploads/
└── instance/             # created automatically
```
