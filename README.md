# DropoutGuard

This project is a full-stack student support and dropout-risk monitoring application built for the Smart India Hackathon theme.

## Project structure

- `frontend/` – Vite + React dashboard and student-support UI
- `backend/` – Flask API, SQLite database, ML training pipeline, and demo data

## Quick start

### 1) Install frontend dependencies

```bash
cd frontend
npm install
```

### 2) Install backend dependencies

```bash
cd backend
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

In Windows PowerShell, use `Copy-Item .env.example .env` instead.

For Brevo email verification, set `BREVO_API_KEY` to a Brevo API key and
`BREVO_FROM_EMAIL` to a verified sender address in `backend/.env`. Email is sent
server-to-server over HTTPS using Brevo's transactional email API; keep the API
key on the backend and never expose it in frontend code. Optionally set
`BREVO_SENDER_NAME`. Generate a private `SECRET_KEY` and never commit `.env`;
it is ignored by Git.

The login page supports sign-in and email registration. New registrations must
verify ownership of the address with an emailed code and are assigned the
Faculty role; Management access is not self-assignable. Existing accounts and
the optional `FACULTY_EMAILS` / `MANAGEMENT_EMAILS` comma-separated allowlists
are used to determine existing staff roles. The pre-seeded
`faculty@college.edu` and `admin@college.edu` accounts are demo addresses, not
real mailboxes. `COOKIE_SECURE=true` should be set when serving the app over
HTTPS.

### 3) Start backend

```bash
cd backend
python app.py
```

The backend serves on http://localhost:5000.

### 4) Start frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

The frontend is usually available at http://localhost:5173.

## Demo credentials

- Management: admin@college.edu
- Faculty: faculty@college.edu

Register a new address by choosing **Register**, entering a name and email,
and verifying the emailed six-digit code. After registration, use **Sign in**
with that email; sign-in codes expire after five minutes and can be resent
after one minute. The page reports email delivery errors instead of showing a
false sent confirmation.

## API notes

- Flask endpoints are served under `/api`
- Email sign-in uses `POST /api/auth/request-otp` and `POST /api/auth/verify-otp`
- OTPs expire after five minutes, allow five verification attempts, and can be resent after one minute
- Student and dashboard APIs require the signed-in HTTP-only session cookie; sessions expire after eight hours
- Upload CSVs through Dataset & Model, or download the generic example template from that page
- CSVs can contain any student attributes or indicators with descriptive headers; student IDs are optional and generated when omitted
- The student directory reads year and semester from separate columns or a combined `year_sem` value (including Roman-numeral years), and displays uploaded last-counseling/counselling dates
- Available numeric and status indicators are analyzed to provide an advisory risk estimate; unsupported custom values are preserved with the student record
- Model training is optional and uses the supplied feature columns; it requires a binary or Low/Medium/High outcome column such as `risk_status`, `status`, `dropout_status`, or `outcome`
- Upload limit: 16 MB. Replacing an existing upload requires confirmation.
- The ML pipeline saves a trained model to `backend/trained_model.joblib`

## Basic validation

```bash
cd backend
pytest tests/test_api.py -q
```

## Notes

- The platform is designed for student support and human review, not punitive decisions.
- Risk scores are advisory and the system clearly distinguishes between observed facts and model estimates.
