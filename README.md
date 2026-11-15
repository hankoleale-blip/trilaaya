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


## Premium interaction upgrade
The frontend now includes a lightweight reusable reveal layer (`frontend/app/motion.tsx`), page entrance transitions, a responsive animated mobile navigation panel, hero motion, refined hover/focus states, and reduced-motion support. Registration forms retain their original fields and API requests; submit buttons now communicate their in-progress state. No backend code, environment variable names, routes, API endpoints, or deployment configuration were changed.

The animation layer uses browser-native CSS transitions and `IntersectionObserver` rather than adding a runtime dependency. A Motion for React installation was attempted during the upgrade but the package registry timed out, so the project deliberately remains dependency-free for animation and can be installed using its existing `package.json`.

## Athletic visual redesign
- Updated the frontend visual system to Deep Navy `#101B2D`, Athletic Lime `#C7F464`, Ice White `#F7F9FC`, Action Blue `#2563EB`, Slate `#64748B`, and Dark Background `#0B1220`.
- Reworked the public homepage around Taekwondo training, with an original locally bundled sports-training image at `frontend/public/images/taekwondo-training.png`.
- Refreshed role selection, role-specific sign-in foundations, Parent/Coach application forms, and the private Admin placeholder.
- Kept the existing Trikaaya logo, Manrope font, routes, registration field names, API URLs, `NEXT_PUBLIC_API_URL`, backend, and deployment configuration intact.
- The uploaded source project does not yet include Parent, Coach, or Admin dashboard implementations or the requested dashboard modules. Those screens have not been fabricated as static dashboards; they remain future backend/product work.
- Existing authentication is still a UI foundation only. Registration forms continue to submit to the existing API.
- Build verification could not be completed in the editing environment because the package registry timed out during `npm install`, leaving Next.js unavailable (`next: not found`). Run `npm install` and `npm run build` in the frontend directory before deployment.
