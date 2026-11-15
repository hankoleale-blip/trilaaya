import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Trikaaya Sports API", version="0.1.0")
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

client = None
db = None
mongo_url = os.getenv("MONGODB_URL")
if mongo_url:
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        db = client[os.getenv("MONGODB_DB", "trikaaya_sports")]
        db.parent_applications.create_index("email", unique=True)
        db.coach_applications.create_index("email", unique=True)
    except Exception:
        client = None
        db = None

class ParentApplication(BaseModel):
    parent_name: str = Field(min_length=2, max_length=120)
    mobile: str = Field(min_length=8, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    address: str = Field(min_length=3, max_length=300)
    student_name: str = Field(min_length=2, max_length=120)
    date_of_birth: str
    gender: str
    emergency_contact: str
    medical_info: Optional[str] = None
    society_name: str = Field(min_length=2, max_length=150)

class CoachApplication(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    mobile: str = Field(min_length=8, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    selected_society: str = Field(min_length=2, max_length=150)

@app.get("/health")
def health():
    return {"status": "ok", "database_configured": db is not None}

def require_database():
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not configured. Set MONGODB_URL in backend/.env.")

@app.post("/registrations/parent", status_code=201)
def parent_registration(data: ParentApplication):
    require_database()
    doc = data.model_dump()
    # Phase 1 stores a pending application only. Password activation/authentication is implemented in a later secure auth stage.
    doc.pop("password", None)
    doc.update({"status": "pending", "submitted_at": datetime.now(timezone.utc), "role": "parent"})
    try:
        result = db.parent_applications.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An application already exists for this email.")
    return {"id": str(result.inserted_id), "status": "pending"}

@app.post("/registrations/coach", status_code=201)
def coach_registration(data: CoachApplication):
    require_database()
    doc = data.model_dump()
    doc.pop("password", None)
    doc.update({"status": "pending", "submitted_at": datetime.now(timezone.utc), "role": "coach"})
    try:
        result = db.coach_applications.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An application already exists for this email.")
    return {"id": str(result.inserted_id), "status": "pending"}
