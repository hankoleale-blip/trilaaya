# Trikaaya Sports — Phase 1

This is the first build stage of the Trikaaya Sports platform. It establishes the visual system, public website, role-selection sign-in, parent/coach application forms, and a FastAPI + MongoDB backend foundation.

## Brand and design
- Brand: Trikaaya Sports
- Tagline: TRI · FORM · BODY
- Phone: +91 99702 97708
- Email: Info@trikaaya.com
- Palette: dark olive `#20251F`, lemon `#E8EF63`, white `#FFFFFF`, soft cream `#F4F5E9`, olive `#A8B33B`
- Font: Manrope
- Responsive, mobile-first layout

## Requirements
- Node.js 20+
- Python 3.11+
- MongoDB Atlas database (or local MongoDB)

## 1. Run the frontend
Open a terminal in `frontend`:

```bash
npm install
cp .env.example .env.local
npm run dev
```

On Windows PowerShell, use:
```powershell
Copy-Item .env.example .env.local
```

Open http://localhost:3000

## 2. Run the backend
Open another terminal in `backend`:

```bash
python -m venv .venv
```

Windows:
```powershell
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

macOS/Linux:
```bash
source .venv/bin/activate
cp .env.example .env
```

Then:
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend health: http://localhost:8000/health
API docs: http://localhost:8000/docs

## Environment configuration
Set `MONGODB_URL` and `MONGODB_DB` in `backend/.env`.
Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.

Do not commit `.env`, `.env.local`, credentials, database URLs, or secret keys.

## Deployment overview
- Frontend: import the `frontend` folder/repository into Vercel. If the repository contains both folders, set Vercel Root Directory to `frontend`.
- Backend: deploy the `backend` folder to Render as a Python web service. Start command:
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Configure the environment variables on Render and Vercel.

## Current functionality and limitations
- Public homepage and navigation are implemented.
- Parent and coach registration forms submit to the backend API.
- The backend stores registration applications in MongoDB with `pending` status.
- Sign-in role selection and role-specific sign-in screens are present as UI foundations.
- Authentication, admin approval screens, student/society workflows, attendance, fee verification, UPI screenshot storage, PDF receipts, competitions, and reporting are planned for subsequent stages.
- No demo accounts, sample societies, sample students, or fake payment records are included.
- Never enter real passwords or sensitive data until the authentication implementation is completed.
