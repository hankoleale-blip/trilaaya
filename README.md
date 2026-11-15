# Trikaaya Sports — Integrated Platform

This project builds on the existing Phase 2 Admin Authentication release. It keeps the original Next.js 14 frontend, FastAPI backend, MongoDB database, private Admin bootstrap, Argon2 password hashes, and the existing `admins`, `admin_sessions`, `admin_login_attempts`, `parent_applications`, and `coach_applications` collections. New workflows use additive collections and indexes; the application does not drop collections or run destructive migrations.

## Included workflows

### Public website and applications
- Existing public Trikaaya Sports website and Parent / Coach application forms are retained.
- Parent and Coach applications remain `pending` until an Admin reviews them.
- New applications store only an Argon2 password hash, never the submitted plain-text password.
- Approval creates or links the relevant account. A Parent's first child is linked to a matching active society by name; if no match exists, the child remains inactive until Admin assigns a society.

### Admin (`/admin`)
- Existing private Admin sign-in and protected dashboard are retained.
- Overview counts are read from MongoDB; no demo statistics or fake records are seeded.
- Review Parent and Coach applications and parent Add Child requests.
- Create societies and set the monthly fee per student.
- Create/manage student and coach records, assign coaches to societies, link students to parent accounts, and activate existing Parent accounts by setting a password.
- View attendance and correct a record; every correction writes an `attendance_audit` entry.
- Generate one invoice per active enrolled student per month. Existing student/month invoices are not duplicated and the fee is snapshotted at generation time.
- Review payment screenshots, UTR, amount and date. Approve or reject manually; only approval changes invoice paid totals/status. Multiple partial payments are supported.
- Configure UPI ID, payee name and QR image.
- Create competitions/events and view summary reports.

### Parent (`/signin/parent` → `/parent/dashboard`)
- One account can access all linked children and select each child's records.
- View attendance, invoices, payment history, UPI instructions and rejection reasons.
- Request additional children; Admin approval is required before the child is linked.
- Submit a payment amount, UTR, payment date and PNG/JPEG screenshot (maximum 5 MB). Submission status is `In Process`; screenshots never mark an invoice paid.
- Download PDF receipts for approved payments.

### Coach (`/signin/coach` → `/coach/dashboard`)
- Coaches can only view assigned societies and active students enrolled in those societies.
- Mark Present/Absent attendance for a selected date and review previous records for assigned societies.
- Duplicate attendance for the same student/date is rejected. Admin can correct a record with an audit entry.

## Requirements
- Node.js 20+
- Python 3.11+
- MongoDB Atlas or another reachable MongoDB deployment

## Backend setup

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -r requirements.txt
```

macOS/Linux:
```bash
source .venv/bin/activate
cp .env.example .env
pip install -r requirements.txt
```

Set `MONGODB_URL`, `MONGODB_DB`, `FRONTEND_ORIGIN`, `ADMIN_JWT_SECRET`, `ADMIN_COOKIE_SECURE`, and `ADMIN_COOKIE_SAMESITE` in `backend/.env`. Generate a signing secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use a secret of at least 32 characters. For local development, `FRONTEND_ORIGIN=http://localhost:3000`, `ADMIN_COOKIE_SECURE=false`, and `ADMIN_COOKIE_SAMESITE=lax` are suitable. In production, use your exact Vercel origin, `ADMIN_COOKIE_SECURE=true`, and normally `ADMIN_COOKIE_SAMESITE=lax` because the frontend proxies API calls server-side.

Start the API from the `backend` directory:

```bash
uvicorn app.main:app --reload
```

API health: http://localhost:8000/health
API docs: http://localhost:8000/docs

### Existing Admin account

There is no public Admin registration route. Keep using the existing Admin account. If this is a fresh database only, create the first Admin privately with:

```bash
python -m app.create_admin
```

The CLI refuses duplicate email addresses and stores an Argon2 password hash. Do not create a second Admin account unless you intend to.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`. Open http://localhost:3000.

## Production deployment

### Backend (Render or equivalent)
- Root directory: `backend`
- Build/install: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Configure all backend environment variables above.

### Frontend (Vercel)
- Root directory: `frontend`
- Configure `NEXT_PUBLIC_API_URL` to the deployed backend URL.
- Deploy the Next.js app.

## Data preservation and rollout

- No destructive database migration is included. Existing Admin records, password hashes, sessions, Parent/Coach applications and their statuses are not reset or rewritten.
- New records use additional collections such as `parents`, `coaches`, `societies`, `students`, `attendance`, `attendance_audit`, `invoices`, `payment_submissions`, `settings`, `competitions`, `child_add_requests`, and `portal_sessions`.
- Startup attempts to create additive indexes. An index conflict is logged and does not disable the existing database connection; application-level duplicate checks remain in place.
- **Take a MongoDB backup/snapshot before deploying the updated backend.** This ZIP does not contain a backup of your live MongoDB database and has not connected to your production database.
- Existing applications remain pending until an Admin reviews them. Old Parent/Coach applications created before password hashes were stored can still be reviewed; after approval, an Admin must set a Parent password in the Parents section before that account can sign in. The same applies to legacy Coach applications without a password hash: create/activate the Coach account from the Coaches section.
- Existing Admin login continues to use the original `admins` collection and private CLI account provisioning. No default credentials are included.

## Security notes
- Admin and Parent/Coach tokens are held in HttpOnly cookies on the frontend origin; API calls are proxied server-side.
- Parent/Coach API endpoints enforce account role and ownership. Parent endpoints are scoped to linked children; Coach endpoints are scoped to assigned societies.
- Payment proof is stored for manual verification. Only Admin approval changes an invoice's paid amount/status.
- Never commit `.env`, `.env.local`, MongoDB credentials, signing secrets, or passwords.

## Important deployment check
This package was prepared without access to your live MongoDB connection or hosting environment. Run the setup steps and test the login flows against a staging database before production deployment. The existing live database was not modified by preparing this ZIP.
