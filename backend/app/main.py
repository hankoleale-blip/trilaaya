import os, secrets, hashlib, base64, io
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Any
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from pwdlib import PasswordHash
import jwt
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Trikaaya Sports API", version="1.0.0")
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
client = None; db = None
mongo_url = os.getenv("MONGODB_URL")
if mongo_url:
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[os.getenv("MONGODB_DB", "trikaaya_sports")]
        # Additive indexes only. An index conflict is logged but never disables access
        # to the existing database or changes existing documents.
        for collection, keys, unique in [
            ("parent_applications", [("email",1)], True), ("coach_applications", [("email",1)], True),
            ("admins", [("email",1)], True), ("parents", [("email",1)], True), ("coaches", [("email",1)], True), ("admin_sessions", [("jti",1)], True),
            ("attendance", [("student_id",1),("date",1)], True),
            ("invoices", [("student_id",1),("month",1)], True),
            ("portal_sessions", [("jti",1)], True),
        ]:
            try: db[collection].create_index(keys, unique=unique)
            except Exception as index_error: print(f"Index setup warning for {collection}: {index_error}")
        for collection in ("admin_sessions", "portal_sessions"):
            try: db[collection].create_index("expires_at", expireAfterSeconds=0)
            except Exception as index_error: print(f"TTL index setup warning for {collection}: {index_error}")
        try: db.payment_submissions.create_index([("student_id",1),("created_at",-1)])
        except Exception as index_error: print(f"Payment index setup warning: {index_error}")
    except Exception as connection_error:
        print(f"MongoDB connection unavailable: {connection_error}")
        client = None; db = None

password_hasher = PasswordHash.recommended()
ADMIN_COOKIE_NAME = "trikaaya_admin_session"; ADMIN_TOKEN_ISSUER = "trikaaya-sports-api"
PARENT_ROLE = "parent"; COACH_ROLE = "coach"

def now_utc(): return datetime.now(timezone.utc)
def mongo_now(): return now_utc().replace(tzinfo=None)
def oid(value: str):
    try: return ObjectId(value)
    except Exception: raise HTTPException(400, "Invalid record ID.")
def find_active_society(name: str):
    target=(name or "").strip().casefold()
    if not target: return None
    for society in db.societies.find({"active":True}):
        if str(society.get("name","")).strip().casefold()==target: return society
    return None

def clean(doc):
    if doc is None: return None
    if isinstance(doc, list): return [clean(x) for x in doc]
    if isinstance(doc, dict): return {("id" if k == "_id" else k): clean(v) for k,v in doc.items() if k not in {"password_hash"}}
    if isinstance(doc, ObjectId): return str(doc)
    if isinstance(doc, datetime): return doc.isoformat()
    return doc
def require_database():
    if db is None: raise HTTPException(503, "Database is not configured. Set MONGODB_URL in backend/.env.")
def verify_admin_origin(request: Request):
    origin=request.headers.get("origin")
    if origin and origin.rstrip("/") not in {x.rstrip("/") for x in origins}: raise HTTPException(403,"Request origin is not allowed.")
def admin_auth_config():
    secret=os.getenv("ADMIN_JWT_SECRET","")
    if len(secret)<32: raise HTTPException(503,"Admin authentication is not configured. Set ADMIN_JWT_SECRET on the backend.")
    try: expiry=int(os.getenv("ADMIN_JWT_EXPIRE_MINUTES","60"))
    except ValueError: raise HTTPException(503,"ADMIN_JWT_EXPIRE_MINUTES must be an integer.")
    if not 5<=expiry<=1440: raise HTTPException(503,"ADMIN_JWT_EXPIRE_MINUTES must be between 5 and 1440.")
    same=os.getenv("ADMIN_COOKIE_SAMESITE","lax").lower(); secure=os.getenv("ADMIN_COOKIE_SECURE","false").lower() in {"1","true","yes"}
    if same not in {"lax","strict","none"} or (same=="none" and not secure): raise HTTPException(503,"Invalid Admin cookie configuration.")
    return secret,expiry,same,secure
def create_token(subject, email, role, minutes, secret):
    now=now_utc(); jti=secrets.token_urlsafe(24)
    payload={"sub":str(subject),"email":email,"role":role,"jti":jti,"iss":ADMIN_TOKEN_ISSUER,"iat":now,"exp":now+timedelta(minutes=minutes)}
    return jwt.encode(payload,secret,algorithm="HS256"),jti,payload["exp"]
def decode_token(token):
    secret,_,_,_=admin_auth_config()
    try: return jwt.decode(token,secret,algorithms=["HS256"],issuer=ADMIN_TOKEN_ISSUER,options={"require":["exp","iat","sub","role","jti"]})
    except jwt.PyJWTError: raise HTTPException(401,"Session is invalid or expired.")
def get_admin_session(request: Request):
    token=request.cookies.get(ADMIN_COOKIE_NAME)
    if not token: raise HTTPException(401,"Admin sign-in is required.")
    payload=decode_token(token); require_database()
    if payload.get("role")!="admin": raise HTTPException(401,"Admin sign-in is required.")
    try: aid=oid(payload["sub"])
    except HTTPException: raise HTTPException(401,"Admin session is invalid.")
    session=db.admin_sessions.find_one({"jti":payload["jti"],"admin_id":aid,"expires_at":{"$gt":mongo_now()}})
    admin=db.admins.find_one({"_id":aid,"active":True},{"password_hash":0})
    if not session or not admin: raise HTTPException(401,"Admin session is invalid or expired.")
    return admin

def admin_dep(request: Request): return get_admin_session(request)
def portal_user(request: Request, role: Optional[str]=None):
    require_database(); auth=request.headers.get("authorization","")
    token=auth[7:] if auth.lower().startswith("bearer ") else ""
    if not token: raise HTTPException(401,"Please sign in.")
    payload=decode_token(token); actual=payload.get("role")
    if actual not in {PARENT_ROLE,COACH_ROLE} or (role and actual!=role): raise HTTPException(403,"This account cannot access this area.")
    try: user_id=oid(payload["sub"])
    except HTTPException: raise HTTPException(401,"Invalid session.")
    session=db.portal_sessions.find_one({"jti":payload["jti"],"user_id":user_id,"role":actual,"expires_at":{"$gt":mongo_now()}})
    collection="parents" if actual==PARENT_ROLE else "coaches"
    user=db[collection].find_one({"_id":user_id,"active":True},{"password_hash":0})
    if not session or not user: raise HTTPException(401,"Session expired. Please sign in again.")
    return {"user":user,"role":actual}
def parent_dep(request: Request): return portal_user(request,PARENT_ROLE)
def coach_dep(request: Request): return portal_user(request,COACH_ROLE)
def require_admin(admin=Depends(admin_dep)): return admin

def app_model_dump(model): return model.model_dump()
class AdminLogin(BaseModel): email: EmailStr; password: str=Field(min_length=1,max_length=256)
class PortalLogin(BaseModel): role: str; email: EmailStr; password: str=Field(min_length=1,max_length=256)
class ParentApplication(BaseModel):
    parent_name:str=Field(min_length=2,max_length=120); mobile:str=Field(min_length=8,max_length=20); email:EmailStr
    password:str=Field(min_length=8,max_length=128); address:str=Field(min_length=3,max_length=300)
    student_name:str=Field(min_length=2,max_length=120); date_of_birth:str; gender:str; emergency_contact:str
    medical_info:Optional[str]=None; society_name:str=Field(min_length=2,max_length=150)
class CoachApplication(BaseModel):
    full_name:str=Field(min_length=2,max_length=120); mobile:str=Field(min_length=8,max_length=20)
    email:EmailStr; password:str=Field(min_length=8,max_length=128); selected_society:str=Field(min_length=2,max_length=150)
class SocietyIn(BaseModel): name:str=Field(min_length=2,max_length=150); address:str=""; sport:str=""; monthly_fee:float=Field(ge=0); schedule:str=""; active:bool=True
class StudentIn(BaseModel): name:str=Field(min_length=2,max_length=120); date_of_birth:str=""; gender:str=""; society_id:str; parent_id:Optional[str]=None; parent_name:str=""; emergency_contact:str=""; medical_info:str=""; active:bool=True
class CoachIn(BaseModel): full_name:str; email:EmailStr; mobile:str=""; society_ids:list[str]=[]; active:bool=True; password:Optional[str]=None
class AttendanceIn(BaseModel): society_id:str; date:str; records:list[dict]
class PaymentIn(BaseModel): invoice_id:str; amount:float=Field(gt=0); utr:str=Field(min_length=6,max_length=80); payment_date:str; screenshot_base64:str
class ReviewIn(BaseModel): action:str; reason:Optional[str]=None
class SettingsIn(BaseModel): upi_id:str=""; upi_name:str=""; qr_image_base64:Optional[str]=None; qr_image_type:Optional[str]=None
class CompetitionIn(BaseModel): name:str; date:str; venue:str=""; society_ids:list[str]=[]; details:str=""; status:str="upcoming"

@app.get("/health")
def health(): return {"status":"ok","database_configured":db is not None}

@app.post("/admin/auth/login")
def admin_login(data:AdminLogin,request:Request,response:Response):
    verify_admin_origin(request); require_database(); secret,minutes,_,_=admin_auth_config()
    ip=request.client.host if request.client else "unknown"; key=hashlib.sha256(ip.encode()).hexdigest(); now=mongo_now()
    attempt=db.admin_login_attempts.find_one({"_id":key})
    if attempt and attempt.get("window_started_at") and attempt["window_started_at"]>now-timedelta(minutes=15) and attempt.get("attempts",0)>=5: raise HTTPException(429,"Too many unsuccessful sign-in attempts. Please try again in 15 minutes.")
    email=str(data.email).lower().strip(); admin=db.admins.find_one({"email":email,"active":True}); valid=False
    if admin:
        try: valid=password_hasher.verify(data.password,admin.get("password_hash",""))
        except Exception: valid=False
    if not valid:
        if attempt and attempt.get("window_started_at") and attempt["window_started_at"]>now-timedelta(minutes=15): db.admin_login_attempts.update_one({"_id":key},{"$inc":{"attempts":1}})
        else: db.admin_login_attempts.update_one({"_id":key},{"$set":{"attempts":1,"window_started_at":now}},upsert=True)
        raise HTTPException(401,"Email or password is incorrect.")
    db.admin_login_attempts.delete_one({"_id":key}); token,jti,expires=create_token(admin["_id"],email,"admin",minutes,secret)
    db.admin_sessions.insert_one({"jti":jti,"admin_id":admin["_id"],"created_at":now_utc(),"expires_at":expires.replace(tzinfo=None)})
    _,_,same,secure=admin_auth_config(); response.set_cookie(ADMIN_COOKIE_NAME,token,max_age=minutes*60,httponly=True,secure=secure,samesite=same,path="/")
    response.headers["Cache-Control"]="no-store"; return {"authenticated":True,"email":email}
@app.get("/admin/auth/me")
def admin_me(request:Request,response:Response):
    admin=get_admin_session(request); response.headers["Cache-Control"]="no-store"; return {"authenticated":True,"email":admin["email"],"role":"admin"}
@app.post("/admin/auth/logout")
def admin_logout(request:Request,response:Response):
    verify_admin_origin(request); token=request.cookies.get(ADMIN_COOKIE_NAME)
    if token and db is not None:
        try: db.admin_sessions.delete_one({"jti":decode_token(token)["jti"]})
        except HTTPException: pass
    _,_,same,secure=admin_auth_config(); response.delete_cookie(ADMIN_COOKIE_NAME,path="/",httponly=True,secure=secure,samesite=same); return {"authenticated":False}

@app.post("/portal/auth/login")
def portal_login(data:PortalLogin):
    require_database(); role=data.role.lower()
    if role not in {PARENT_ROLE,COACH_ROLE}: raise HTTPException(400,"Choose Parent or Coach sign-in.")
    email=str(data.email).lower().strip(); collection="parents" if role==PARENT_ROLE else "coaches"
    user=db[collection].find_one({"email":email,"active":True})
    valid=False
    if user:
        try: valid=password_hasher.verify(data.password,user.get("password_hash",""))
        except Exception: valid=False
    if not valid: raise HTTPException(401,"Email or password is incorrect, or your account is not active yet.")
    secret,minutes,_,_=admin_auth_config(); token,jti,expires=create_token(user["_id"],email,role,minutes,secret)
    db.portal_sessions.insert_one({"jti":jti,"user_id":user["_id"],"role":role,"created_at":mongo_now(),"expires_at":expires.replace(tzinfo=None)})
    return {"access_token":token,"token_type":"bearer","expires_in":minutes*60,"role":role,"user":clean(user)}
@app.get("/portal/me")
def portal_me(context=Depends(portal_user)): return {"role":context["role"],"user":clean(context["user"])}
@app.post("/portal/auth/logout")
def portal_logout(request:Request):
    auth=request.headers.get("authorization",""); token=auth[7:] if auth.lower().startswith("bearer ") else ""
    if token:
        try: db.portal_sessions.delete_one({"jti":decode_token(token)["jti"]})
        except Exception: pass
    return {"ok":True}

# Public applications remain pending until an Admin explicitly approves them.
@app.post("/registrations/parent",status_code=201)
def parent_registration(data:ParentApplication):
    require_database(); doc=app_model_dump(data); doc["password_hash"]=password_hasher.hash(doc.pop("password")); doc.update({"status":"pending","submitted_at":now_utc(),"role":"parent"})
    try: result=db.parent_applications.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(409,"An application already exists for this email.")
    return {"id":str(result.inserted_id),"status":"pending"}
@app.post("/registrations/coach",status_code=201)
def coach_registration(data:CoachApplication):
    require_database(); doc=app_model_dump(data); doc["password_hash"]=password_hasher.hash(doc.pop("password")); doc.update({"status":"pending","submitted_at":now_utc(),"role":"coach"})
    try: result=db.coach_applications.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(409,"An application already exists for this email.")
    return {"id":str(result.inserted_id),"status":"pending"}

# Admin: overview and applications
@app.get("/admin/overview")
def admin_overview(admin=Depends(require_admin)):
    require_database(); return {"societies":db.societies.count_documents({}),"students":db.students.count_documents({"active":True}),"coaches":db.coaches.count_documents({"active":True}),"pending_parent_applications":db.parent_applications.count_documents({"status":"pending"}),"pending_coach_applications":db.coach_applications.count_documents({"status":"pending"}),"pending_payments":db.payment_submissions.count_documents({"status":"In Process"}),"attendance_today":db.attendance.count_documents({"date":date.today().isoformat()})}
@app.get("/admin/applications")
def list_applications(status:Optional[str]=None,admin=Depends(require_admin)):
    require_database(); out=[]
    for role,col in [("parent","parent_applications"),("coach","coach_applications")]:
        q={"status":status} if status else {}; out += [{**clean(x),"application_type":role} for x in db[col].find(q).sort("submitted_at",-1)]
    return out
@app.post("/admin/applications/{role}/{application_id}/review")
def review_application(role:str,application_id:str,data:ReviewIn,admin=Depends(require_admin)):
    require_database(); role=role.lower(); col="parent_applications" if role=="parent" else "coach_applications" if role=="coach" else None
    if not col: raise HTTPException(404,"Application type not found.")
    appdoc=db[col].find_one({"_id":oid(application_id)})
    if not appdoc: raise HTTPException(404,"Application not found.")
    if appdoc.get("status")!="pending": raise HTTPException(409,"This application has already been reviewed.")
    action=data.action.lower()
    if action not in {"approve","reject"}: raise HTTPException(400,"Choose approve or reject.")
    if action=="reject":
        db[col].update_one({"_id":appdoc["_id"],"status":"pending"},{"$set":{"status":"rejected","review_reason":(data.reason or "Application not approved.")[:500],"reviewed_at":now_utc(),"reviewed_by":str(admin["_id"])}})
        return {"status":"rejected"}
    email=appdoc["email"].lower()
    if role=="parent":
        existing=db.parents.find_one({"email":email})
        parent_id=existing["_id"] if existing else db.parents.insert_one({"email":email,"parent_name":appdoc["parent_name"],"mobile":appdoc["mobile"],"address":appdoc.get("address",""),"password_hash":appdoc.get("password_hash"),"active":bool(appdoc.get("password_hash")),"created_at":now_utc()}).inserted_id
        student={"name":appdoc["student_name"],"date_of_birth":appdoc.get("date_of_birth",""),"gender":appdoc.get("gender",""),"society_id":None,"requested_society":appdoc.get("society_name",""),"parent_id":parent_id,"parent_name":appdoc["parent_name"],"emergency_contact":appdoc.get("emergency_contact",""),"medical_info":appdoc.get("medical_info",""),"active":False,"approval_status":"pending_society_assignment","created_at":now_utc()}
        # Match requested society by name; never invent or create a society automatically.
        society=find_active_society(appdoc.get("society_name",""))
        if society: student.update({"society_id":society["_id"],"active":True,"approval_status":"approved"})
        db.students.insert_one(student)
        if existing and appdoc.get("password_hash") and not existing.get("password_hash"): db.parents.update_one({"_id":parent_id},{"$set":{"password_hash":appdoc["password_hash"],"active":True}})
    else:
        existing=db.coaches.find_one({"email":email})
        if not existing:
            society=find_active_society(appdoc.get("selected_society",""))
            db.coaches.insert_one({"email":email,"full_name":appdoc["full_name"],"mobile":appdoc["mobile"],"password_hash":appdoc.get("password_hash"),"society_ids":[society["_id"]] if society else [],"active":bool(appdoc.get("password_hash")),"created_at":now_utc()})
    db[col].update_one({"_id":appdoc["_id"],"status":"pending"},{"$set":{"status":"approved","reviewed_at":now_utc(),"reviewed_by":str(admin["_id"])}})
    return {"status":"approved","note":"Parent child is active only when a matching active society exists."}

# Admin: societies, students, coaches
@app.get("/admin/societies")
def societies(admin=Depends(require_admin)): require_database(); return clean(list(db.societies.find().sort("name",1)))
@app.post("/admin/societies",status_code=201)
def create_society(data:SocietyIn,admin=Depends(require_admin)):
    require_database(); doc=app_model_dump(data)
    if any(str(x.get("name","")).strip().casefold()==data.name.strip().casefold() for x in db.societies.find({}, {"name":1})): raise HTTPException(409,"A society with this name already exists.")
    doc.update({"created_at":now_utc(),"created_by":str(admin["_id"])})
    try: res=db.societies.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(409,"Society already exists.")
    return clean(db.societies.find_one({"_id":res.inserted_id}))
@app.patch("/admin/societies/{sid}")
def update_society(sid:str,data:dict,admin=Depends(require_admin)):
    allowed={"name","address","sport","monthly_fee","schedule","active"}; update={k:v for k,v in data.items() if k in allowed}
    if "monthly_fee" in update and float(update["monthly_fee"])<0: raise HTTPException(400,"Monthly fee cannot be negative.")
    result=db.societies.update_one({"_id":oid(sid)},{"$set":update})
    if not result.matched_count: raise HTTPException(404,"Society not found.")
    return clean(db.societies.find_one({"_id":oid(sid)}))
@app.get("/admin/students")
def students(society_id:Optional[str]=None,admin=Depends(require_admin)):
    require_database(); q={}
    if society_id: q["society_id"]=oid(society_id)
    return clean(list(db.students.find(q).sort("name",1)))
@app.post("/admin/students",status_code=201)
def create_student(data:StudentIn,admin=Depends(require_admin)):
    require_database(); society=db.societies.find_one({"_id":oid(data.society_id),"active":True})
    if not society: raise HTTPException(400,"Choose an active society.")
    doc=app_model_dump(data); doc["society_id"]=society["_id"]
    if doc.get("parent_id"): doc["parent_id"]=oid(doc["parent_id"])
    doc.update({"created_at":now_utc(),"approval_status":"approved"}); res=db.students.insert_one(doc); return clean(db.students.find_one({"_id":res.inserted_id}))
@app.patch("/admin/students/{sid}")
def update_student(sid:str,data:dict,admin=Depends(require_admin)):
    allowed={"name","date_of_birth","gender","society_id","parent_id","parent_name","emergency_contact","medical_info","active"}; u={k:v for k,v in data.items() if k in allowed}
    for key in ("society_id","parent_id"):
        if u.get(key): u[key]=oid(u[key])
    result=db.students.update_one({"_id":oid(sid)},{"$set":u})
    if not result.matched_count: raise HTTPException(404,"Student not found.")
    return clean(db.students.find_one({"_id":oid(sid)}))
@app.get("/admin/coaches")
def coaches(admin=Depends(require_admin)): require_database(); return clean(list(db.coaches.find().sort("full_name",1)))
@app.post("/admin/coaches",status_code=201)
def create_coach(data:CoachIn,admin=Depends(require_admin)):
    require_database(); email=str(data.email).lower()
    if db.coaches.find_one({"email":email}): raise HTTPException(409,"A coach already exists for this email.")
    doc=app_model_dump(data); doc["email"]=email; doc["society_ids"]=[oid(x) for x in data.society_ids]; doc["active"]=data.active; doc["created_at"]=now_utc()
    if data.password: doc["password_hash"]=password_hasher.hash(data.password)
    else: doc["active"]=False
    doc.pop("password",None)
    try: res=db.coaches.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(409,"A coach already exists for this email.")
    return clean(db.coaches.find_one({"_id":res.inserted_id}))
@app.patch("/admin/coaches/{cid}")
def update_coach(cid:str,data:dict,admin=Depends(require_admin)):
    allowed={"full_name","mobile","active"}; u={k:v for k,v in data.items() if k in allowed}
    if "society_ids" in data: u["society_ids"]=[oid(x) for x in data["society_ids"]]
    if data.get("password"): u["password_hash"]=password_hasher.hash(data["password"])
    r=db.coaches.update_one({"_id":oid(cid)},{"$set":u})
    if not r.matched_count: raise HTTPException(404,"Coach not found.")
    return clean(db.coaches.find_one({"_id":oid(cid)}))

# Attendance: unique student/date index prevents duplicate entries. Admin edits are audited.
@app.post("/admin/attendance")
def admin_attendance(data:AttendanceIn,admin=Depends(require_admin)):
    require_database(); society=oid(data.society_id)
    try: day=date.fromisoformat(data.date).isoformat()
    except ValueError: raise HTTPException(400,"Attendance date must use YYYY-MM-DD format.")
    inserted=0
    for rec in data.records:
        student_id=oid(rec["student_id"]); status=rec.get("status")
        if status not in {"Present","Absent"}: raise HTTPException(400,"Attendance status must be Present or Absent.")
        student=db.students.find_one({"_id":student_id,"society_id":society,"active":True})
        if not student: raise HTTPException(400,"A selected student is not active in this society.")
        if db.attendance.find_one({"student_id":student_id,"date":day}): raise HTTPException(409,f"Attendance already exists for {student.get('name')} on {day}. Use the correction action instead.")
        try: db.attendance.insert_one({"student_id":student_id,"society_id":society,"date":day,"status":status,"coach_id":None,"marked_by":str(admin["_id"]),"created_at":now_utc(),"updated_at":now_utc()}); inserted+=1
        except DuplicateKeyError: raise HTTPException(409,f"Attendance already exists for {student.get('name')} on {day}. Use the correction action instead.")
    return {"saved":inserted}
@app.get("/admin/attendance")
def admin_attendance_list(date_from:Optional[str]=None,date_to:Optional[str]=None,society_id:Optional[str]=None,admin=Depends(require_admin)):
    q={}
    if date_from or date_to: q["date"]={**({"$gte":date_from} if date_from else {}),**({"$lte":date_to} if date_to else {})}
    if society_id: q["society_id"]=oid(society_id)
    rows=list(db.attendance.find(q).sort([("date",-1)])); out=[]
    for x in rows:
        s=db.students.find_one({"_id":x["student_id"]},{"name":1}); so=db.societies.find_one({"_id":x["society_id"]},{"name":1})
        out.append({**clean(x),"student_name":s.get("name") if s else "Unknown","society_name":so.get("name") if so else "Unknown"})
    return out
@app.patch("/admin/attendance/{aid}")
def correct_attendance(aid:str,data:dict,admin=Depends(require_admin)):
    record=db.attendance.find_one({"_id":oid(aid)})
    if not record: raise HTTPException(404,"Attendance record not found.")
    status=data.get("status")
    if status not in {"Present","Absent"}: raise HTTPException(400,"Status must be Present or Absent.")
    db.attendance_audit.insert_one({"attendance_id":record["_id"],"old_status":record["status"],"new_status":status,"reason":str(data.get("reason","Admin correction"))[:500],"changed_by":str(admin["_id"]),"changed_at":now_utc()})
    db.attendance.update_one({"_id":record["_id"]},{"$set":{"status":status,"updated_at":now_utc(),"corrected_by":str(admin["_id"])}}); return {"status":status,"audit_logged":True}

# Monthly invoices are idempotent per child/month. Society fee is snapshotted on invoice creation.
@app.post("/admin/invoices/generate")
def generate_invoices(data:dict,admin=Depends(require_admin)):
    require_database(); month=str(data.get("month",""))
    try: datetime.strptime(month,"%Y-%m")
    except ValueError: raise HTTPException(400,"Month must use YYYY-MM format.")
    created=0; existing=0
    for student in db.students.find({"active":True,"society_id":{"$ne":None}}):
        society=db.societies.find_one({"_id":student["society_id"]})
        if not society: continue
        if db.invoices.find_one({"student_id":student["_id"],"month":month}): existing+=1; continue
        amount=float(society.get("monthly_fee",0)); db.invoices.insert_one({"student_id":student["_id"],"parent_id":student.get("parent_id"),"society_id":society["_id"],"month":month,"amount":amount,"paid_amount":0.0,"status":"Pending","created_at":now_utc()}); created+=1
    return {"created":created,"already_existed":existing,"month":month}
@app.get("/admin/invoices")
def admin_invoices(status:Optional[str]=None,month:Optional[str]=None,admin=Depends(require_admin)):
    q={}
    if status: q["status"]=status
    if month: q["month"]=month
    out=[]
    for x in db.invoices.find(q).sort("month",-1):
        s=db.students.find_one({"_id":x["student_id"]}); so=db.societies.find_one({"_id":x["society_id"]})
        out.append({**clean(x),"student_name":s.get("name") if s else "Unknown","society_name":so.get("name") if so else "Unknown"})
    return out
@app.get("/admin/payments")
def admin_payments(status:Optional[str]=None,admin=Depends(require_admin)):
    q={"status":status} if status else {}; out=[]
    for p in db.payment_submissions.find(q,{"screenshot_data":0}).sort("created_at",-1):
        s=db.students.find_one({"_id":p["student_id"]}); out.append({**clean(p),"student_name":s.get("name") if s else "Unknown"})
    return out
@app.post("/admin/payments/{pid}/review")
def review_payment(pid:str,data:ReviewIn,admin=Depends(require_admin)):
    p=db.payment_submissions.find_one({"_id":oid(pid)})
    if not p: raise HTTPException(404,"Payment submission not found.")
    if p["status"]!="In Process": raise HTTPException(409,"This payment has already been reviewed.")
    action=data.action.lower()
    if action not in {"approve","reject"}: raise HTTPException(400,"Choose approve or reject.")
    if action=="reject":
        db.payment_submissions.update_one({"_id":p["_id"],"status":"In Process"},{"$set":{"status":"Rejected","rejection_reason":(data.reason or "Payment could not be verified.")[:500],"reviewed_at":now_utc(),"reviewed_by":str(admin["_id"])}}); return {"status":"Rejected"}
    inv=db.invoices.find_one({"_id":p["invoice_id"]})
    if not inv: raise HTTPException(404,"Invoice no longer exists.")
    approved=db.payment_submissions.find({"invoice_id":inv["_id"],"status":"Approved"}); paid=sum(float(x.get("amount",0)) for x in approved)+float(p["amount"])
    if paid>float(inv["amount"])+0.001: raise HTTPException(409,"Approving this payment would exceed the invoice balance.")
    db.payment_submissions.update_one({"_id":p["_id"],"status":"In Process"},{"$set":{"status":"Approved","reviewed_at":now_utc(),"reviewed_by":str(admin["_id"])}})
    new_status="Paid" if paid+0.001>=float(inv["amount"]) else "Partially Paid"
    db.invoices.update_one({"_id":inv["_id"]},{"$set":{"paid_amount":round(paid,2),"status":new_status}})
    return {"status":"Approved","invoice_status":new_status,"paid_amount":round(paid,2)}
@app.get("/admin/payments/{pid}/screenshot")
def payment_screenshot(pid:str,admin=Depends(require_admin)):
    p=db.payment_submissions.find_one({"_id":oid(pid)})
    if not p or not p.get("screenshot_data"): raise HTTPException(404,"Screenshot not found.")
    raw=base64.b64decode(p["screenshot_data"]); return StreamingResponse(io.BytesIO(raw),media_type=p.get("screenshot_type","image/jpeg"),headers={"Content-Disposition":"inline; filename=payment-proof"})

# UPI configuration and downloadable receipts.
@app.get("/admin/settings")
def get_settings(admin=Depends(require_admin)):
    s=db.settings.find_one({"_id":"payments"}) or {}; return {"upi_id":s.get("upi_id",""),"upi_name":s.get("upi_name",""),"qr_image_base64":s.get("qr_image_base64"),"qr_image_type":s.get("qr_image_type","image/png")}
@app.put("/admin/settings")
def update_settings(data:SettingsIn,admin=Depends(require_admin)):
    doc={"upi_id":data.upi_id.strip(),"upi_name":data.upi_name.strip(),"updated_at":now_utc()}
    if data.qr_image_type is not None and data.qr_image_type not in {"image/png","image/jpeg"}: raise HTTPException(400,"QR image must be PNG or JPEG.")
    if data.qr_image_base64 is not None:
        try: qr_raw=base64.b64decode(data.qr_image_base64,validate=True)
        except Exception: raise HTTPException(400,"QR image is invalid.")
        if len(qr_raw)>5*1024*1024: raise HTTPException(413,"QR image must be 5 MB or smaller.")
        if not (qr_raw.startswith(b"\x89PNG") or qr_raw.startswith(b"\xff\xd8")): raise HTTPException(400,"QR image must be PNG or JPEG.")
        doc["qr_image_base64"]=data.qr_image_base64
    if data.qr_image_type is not None: doc["qr_image_type"]=data.qr_image_type
    db.settings.update_one({"_id":"payments"},{"$set":doc},upsert=True); return {"saved":True}
@app.get("/admin/receipts/{pid}")
def admin_receipt(pid:str,admin=Depends(require_admin)):
    return build_receipt(pid)
def build_receipt(pid):
    p=db.payment_submissions.find_one({"_id":oid(pid),"status":"Approved"})
    if not p: raise HTTPException(404,"An approved payment receipt is not available.")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buff=io.BytesIO(); c=canvas.Canvas(buff,pagesize=A4); c.setFont("Helvetica-Bold",20); c.drawString(55,790,"TRIKAAYA SPORTS")
        c.setFont("Helvetica",11); c.drawString(55,755,"OFFICIAL PAYMENT RECEIPT"); c.drawString(55,720,f"Receipt ID: TRI-{str(p['_id'])[-8:].upper()}")
        c.drawString(55,695,f"Payment date: {p.get('payment_date','')}"); c.drawString(55,670,f"UTR / Reference: {p.get('utr','')}")
        c.drawString(55,645,f"Amount received: INR {float(p.get('amount',0)):.2f}")
        inv=db.invoices.find_one({"_id":p["invoice_id"]}); stu=db.students.find_one({"_id":p["student_id"]})
        c.drawString(55,620,f"Student: {(stu or {}).get('name','')}"); c.drawString(55,595,f"Fee month: {(inv or {}).get('month','')}")
        c.drawString(55,570,"Payment status: APPROVED"); c.drawString(55,510,"This receipt confirms that the payment was manually verified by Trikaaya Sports.")
        c.save(); buff.seek(0); return StreamingResponse(buff,media_type="application/pdf",headers={"Content-Disposition":f"attachment; filename=Trikaaya-receipt-{str(p['_id'])[-8:]}.pdf"})
    except ImportError: raise HTTPException(503,"PDF receipt dependency is not installed. Install backend requirements.")

# Competitions and reports
@app.get("/admin/competitions")
def admin_competitions(admin=Depends(require_admin)): return clean(list(db.competitions.find().sort("date",1)))
@app.post("/admin/competitions",status_code=201)
def create_competition(data:CompetitionIn,admin=Depends(require_admin)):
    doc=app_model_dump(data); doc["society_ids"]=[oid(x) for x in data.society_ids]; doc["created_at"]=now_utc(); r=db.competitions.insert_one(doc); return clean(db.competitions.find_one({"_id":r.inserted_id}))
@app.patch("/admin/competitions/{cid}")
def update_competition(cid:str,data:dict,admin=Depends(require_admin)):
    allowed={"name","date","venue","details","status"}; u={k:v for k,v in data.items() if k in allowed}
    if "society_ids" in data: u["society_ids"]=[oid(x) for x in data["society_ids"]]
    r=db.competitions.update_one({"_id":oid(cid)},{"$set":u})
    if not r.matched_count: raise HTTPException(404,"Competition not found.")
    return clean(db.competitions.find_one({"_id":oid(cid)}))
@app.get("/admin/reports/summary")
def reports(admin=Depends(require_admin)):
    return {"students_by_society":[{"society":s["name"],"count":db.students.count_documents({"society_id":s["_id"],"active":True})} for s in db.societies.find()],"invoice_totals":{"count":db.invoices.count_documents({}),"amount":sum(float(x.get("amount",0)) for x in db.invoices.find()),"paid":sum(float(x.get("paid_amount",0)) for x in db.invoices.find())},"attendance_totals":{"present":db.attendance.count_documents({"status":"Present"}),"absent":db.attendance.count_documents({"status":"Absent"})}}

# Parent portal: strictly scoped to children linked to the authenticated parent.
def parent_children(parent): return list(db.students.find({"parent_id":parent["_id"]}).sort("name",1))
def ensure_parent_child(parent,student_id):
    s=db.students.find_one({"_id":oid(student_id),"parent_id":parent["_id"]})
    if not s: raise HTTPException(404,"Child not found in this parent account.")
    return s
@app.get("/parent/children")
def parent_get_children(ctx=Depends(parent_dep)): return clean(parent_children(ctx["user"]))
@app.post("/parent/children",status_code=201)
def parent_add_child(data:dict,ctx=Depends(parent_dep)):
    p=ctx["user"]; required=["name","date_of_birth","society_name"]
    if any(not str(data.get(k,"")).strip() for k in required): raise HTTPException(400,"Child name, date of birth and requested society are required.")
    r=db.child_add_requests.insert_one({"parent_id":p["_id"],"name":data["name"],"date_of_birth":data["date_of_birth"],"gender":data.get("gender",""),"society_name":data["society_name"],"emergency_contact":data.get("emergency_contact",""),"medical_info":data.get("medical_info",""),"status":"pending","created_at":now_utc()})
    return {"id":str(r.inserted_id),"status":"pending_admin_approval"}
@app.get("/parent/attendance")
def parent_attendance(student_id:Optional[str]=None,ctx=Depends(parent_dep)):
    children=parent_children(ctx["user"]); ids=[x["_id"] for x in children]
    if student_id: ensure_parent_child(ctx["user"],student_id); ids=[oid(student_id)]
    return clean(list(db.attendance.find({"student_id":{"$in":ids}}).sort("date",-1)))
@app.get("/parent/invoices")
def parent_invoices(student_id:Optional[str]=None,ctx=Depends(parent_dep)):
    children=parent_children(ctx["user"]); ids=[x["_id"] for x in children]
    if student_id: ensure_parent_child(ctx["user"],student_id); ids=[oid(student_id)]
    out=[]
    for inv in db.invoices.find({"student_id":{"$in":ids}}).sort("month",-1): out.append({**clean(inv),"student_name":next((x["name"] for x in children if x["_id"]==inv["student_id"]),"")})
    return out
@app.get("/parent/settings/payments")
def parent_payment_settings(ctx=Depends(parent_dep)):
    s=db.settings.find_one({"_id":"payments"}) or {}; return {"upi_id":s.get("upi_id",""),"upi_name":s.get("upi_name",""),"qr_image_base64":s.get("qr_image_base64"),"qr_image_type":s.get("qr_image_type","image/png")}
@app.post("/parent/payments",status_code=201)
def submit_payment(data:PaymentIn,ctx=Depends(parent_dep)):
    p=ctx["user"]; inv=db.invoices.find_one({"_id":oid(data.invoice_id)})
    if not inv or inv.get("parent_id")!=p["_id"]: raise HTTPException(404,"Invoice not found in your account.")
    if inv.get("status")=="Paid": raise HTTPException(409,"This invoice is already paid.")
    if db.payment_submissions.find_one({"utr":data.utr.strip()}): raise HTTPException(409,"This UTR has already been submitted.")
    try: date.fromisoformat(data.payment_date)
    except ValueError: raise HTTPException(400,"Payment date must use YYYY-MM-DD format.")
    try: raw=base64.b64decode(data.screenshot_base64.split(",")[-1],validate=True)
    except Exception: raise HTTPException(400,"Payment screenshot is invalid.")
    if len(raw)>5*1024*1024: raise HTTPException(413,"Screenshot must be 5 MB or smaller.")
    if not raw: raise HTTPException(400,"Upload a payment screenshot.")
    approved=sum(float(x.get("amount",0)) for x in db.payment_submissions.find({"invoice_id":inv["_id"],"status":"Approved"}))
    pending=sum(float(x.get("amount",0)) for x in db.payment_submissions.find({"invoice_id":inv["_id"],"status":"In Process"}))
    if data.amount>float(inv["amount"])-approved-pending+0.001: raise HTTPException(400,"Amount exceeds the remaining unsubmitted invoice balance.")
    media="image/png" if raw.startswith(b"\x89PNG") else "image/jpeg" if raw.startswith(b"\xff\xd8") else None
    if not media: raise HTTPException(400,"Upload a PNG or JPEG screenshot.")
    r=db.payment_submissions.insert_one({"invoice_id":inv["_id"],"student_id":inv["student_id"],"parent_id":p["_id"],"amount":round(data.amount,2),"utr":data.utr.strip(),"payment_date":data.payment_date,"screenshot_data":base64.b64encode(raw).decode(),"screenshot_type":media,"status":"In Process","created_at":now_utc()})
    return {"id":str(r.inserted_id),"status":"In Process"}
@app.get("/parent/payments")
def parent_payments(ctx=Depends(parent_dep)):
    out=[]
    for p in db.payment_submissions.find({"parent_id":ctx["user"]["_id"]},{"screenshot_data":0}).sort("created_at",-1):
        student=db.students.find_one({"_id":p["student_id"]},{"name":1})
        out.append({**clean(p),"student_name":(student or {}).get("name","Unknown")})
    return out
@app.get("/parent/receipts/{pid}")
def parent_receipt(pid:str,ctx=Depends(parent_dep)):
    p=db.payment_submissions.find_one({"_id":oid(pid),"parent_id":ctx["user"]["_id"],"status":"Approved"})
    if not p: raise HTTPException(404,"Approved receipt not found.")
    return build_receipt(pid)
@app.get("/parent/competitions")
def parent_competitions(student_id:Optional[str]=None,ctx=Depends(parent_dep)):
    children=parent_children(ctx["user"])
    if student_id: children=[ensure_parent_child(ctx["user"],student_id)]
    sids=list({x.get("society_id") for x in children if x.get("society_id")})
    return clean(list(db.competitions.find({"$or":[{"society_ids":{"$in":sids}},{"society_ids":[]}]}).sort("date",1)))

# Coach portal: only assigned societies and their students are accessible.
@app.get("/coach/societies")
def coach_societies(ctx=Depends(coach_dep)):
    return clean(list(db.societies.find({"_id":{"$in":ctx["user"].get("society_ids",[])},"active":True})))
@app.get("/coach/students")
def coach_students(society_id:str,ctx=Depends(coach_dep)):
    sid=oid(society_id)
    if sid not in ctx["user"].get("society_ids",[]): raise HTTPException(403,"This society is not assigned to your account.")
    return clean(list(db.students.find({"society_id":sid,"active":True}).sort("name",1)))
@app.post("/coach/attendance")
def coach_mark_attendance(data:AttendanceIn,ctx=Depends(coach_dep)):
    coach=ctx["user"]; sid=oid(data.society_id)
    if sid not in coach.get("society_ids",[]): raise HTTPException(403,"This society is not assigned to your account.")
    try: day=date.fromisoformat(data.date).isoformat()
    except ValueError: raise HTTPException(400,"Attendance date must use YYYY-MM-DD format.")
    inserted=0
    for rec in data.records:
        student_id=oid(rec["student_id"]); status=rec.get("status")
        if status not in {"Present","Absent"}: raise HTTPException(400,"Attendance status must be Present or Absent.")
        if not db.students.find_one({"_id":student_id,"society_id":sid,"active":True}): raise HTTPException(400,"Student is not enrolled in this assigned society.")
        if db.attendance.find_one({"student_id":student_id,"date":day}): raise HTTPException(409,"Attendance already submitted for one of these students on this date.")
        try: db.attendance.insert_one({"student_id":student_id,"society_id":sid,"date":day,"status":status,"coach_id":coach["_id"],"marked_by":str(coach["_id"]),"created_at":now_utc(),"updated_at":now_utc()}); inserted+=1
        except DuplicateKeyError: raise HTTPException(409,"Attendance already submitted for one of these students on this date.")
    return {"saved":inserted}
@app.get("/coach/attendance")
def coach_attendance(society_id:Optional[str]=None,ctx=Depends(coach_dep)):
    coach=ctx["user"]; ids=coach.get("society_ids",[])
    if society_id:
        sid=oid(society_id)
        if sid not in ids: raise HTTPException(403,"This society is not assigned to your account.")
        ids=[sid]
    rows=list(db.attendance.find({"society_id":{"$in":ids}}).sort("date",-1)); out=[]
    for x in rows:
        s=db.students.find_one({"_id":x["student_id"]},{"name":1}); out.append({**clean(x),"student_name":(s or {}).get("name","Unknown")})
    return out

@app.get("/")
def root(): return {"service":"Trikaaya Sports API","docs":"/docs"}

@app.get("/admin/child-requests")
def admin_child_requests(status:Optional[str]="pending",admin=Depends(require_admin)):
    q={"status":status} if status else {}; out=[]
    for x in db.child_add_requests.find(q).sort("created_at",-1):
        p=db.parents.find_one({"_id":x["parent_id"]},{"parent_name":1,"email":1})
        out.append({**clean(x),"parent":clean(p)})
    return out
@app.post("/admin/child-requests/{rid}/review")
def review_child_request(rid:str,data:dict,admin=Depends(require_admin)):
    req=db.child_add_requests.find_one({"_id":oid(rid),"status":"pending"})
    if not req: raise HTTPException(404,"Pending child request not found.")
    action=data.get("action")
    if action=="reject":
        db.child_add_requests.update_one({"_id":req["_id"]},{"$set":{"status":"rejected","review_reason":str(data.get("reason","Not approved"))[:500],"reviewed_at":now_utc()}}); return {"status":"rejected"}
    if action!="approve": raise HTTPException(400,"Choose approve or reject.")
    society=find_active_society(req.get("society_name",""))
    if not society: raise HTTPException(400,"Create/activate the requested society first, or ask the parent to submit a matching society name.")
    student={"name":req["name"],"date_of_birth":req["date_of_birth"],"gender":req.get("gender",""),"society_id":society["_id"],"parent_id":req["parent_id"],"parent_name":(db.parents.find_one({"_id":req["parent_id"]}) or {}).get("parent_name",""),"emergency_contact":req.get("emergency_contact",""),"medical_info":req.get("medical_info",""),"active":True,"approval_status":"approved","created_at":now_utc()}
    db.students.insert_one(student); db.child_add_requests.update_one({"_id":req["_id"]},{"$set":{"status":"approved","reviewed_at":now_utc(),"reviewed_by":str(admin["_id"])}}); return {"status":"approved"}

@app.get("/admin/parents")
def admin_parents(admin=Depends(require_admin)):
    return clean(list(db.parents.find({}, {"password_hash":0}).sort("parent_name",1)))
@app.patch("/admin/parents/{pid}/account")
def manage_parent_account(pid:str,data:dict,admin=Depends(require_admin)):
    parent=db.parents.find_one({"_id":oid(pid)})
    if not parent: raise HTTPException(404,"Parent account not found.")
    update={"active":bool(data.get("active",True))}
    if data.get("password"):
        if len(data["password"])<8: raise HTTPException(400,"Password must be at least 8 characters.")
        update["password_hash"]=password_hasher.hash(data["password"])
    db.parents.update_one({"_id":parent["_id"]},{"$set":update}); return {"updated":True,"active":update["active"]}

@app.get("/parent/child-requests")
def parent_child_requests(ctx=Depends(parent_dep)):
    return clean(list(db.child_add_requests.find({"parent_id":ctx["user"]["_id"]}).sort("created_at",-1)))
