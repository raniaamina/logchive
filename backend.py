import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Response, Request, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import dari database.py
from database import Base, engine, SessionLocal, get_db, User, Log, LOGS_DIR

BASE_URL = "http://localhost:8077"

# Auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)
fake_tokens = {}  # token -> username

def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db=Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = fake_tokens.get(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# Schemas
class LogCreate(BaseModel):
    filename: Optional[str]
    content: str
    private: Optional[bool] = False
    expire_minutes: Optional[int] = None

class LogOut(BaseModel):
    id: int
    filename: str
    content: str
    private: bool
    expire_at: Optional[datetime]
    created_at: datetime

# Router tambahan
router = APIRouter()

@router.post("/check_missing_files_all")
def check_and_cleanup_missing_files_all(db=Depends(get_db)):
    logs = db.query(Log).all()
    missing_logs = [log for log in logs if not os.path.exists(os.path.join(LOGS_DIR, log.filename))]

    for log in missing_logs:
        db.delete(log)
    db.commit()
    return {"msg": f"{len(missing_logs)} log(s) removed because file missing"}

# FastAPI app
app = FastAPI(title="SaveLog Simple API")
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8077", "http://127.0.0.1:8077", "http://0.0.0.0:8077"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/logs_public", response_model=List[LogOut])
def get_logs_public(db=Depends(get_db)):
    return db.query(Log).filter(Log.private == False).all()

@app.get("/logs/{filename}")
async def get_log(filename: str, token: Optional[str] = Depends(oauth2_scheme), db=Depends(get_db)):
    log = db.query(Log).filter(Log.filename == filename).first()
    if not log:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    if log.private:
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        username = fake_tokens.get(token)
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.username == username).first()
        if not user or user.id != log.owner_id:
            raise HTTPException(status_code=403, detail="Access denied")

    filepath = os.path.join(LOGS_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(filepath)

@app.post("/register")
def register(username: str, password: str, db=Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username exists")
    user = User(username=username, password=password)
    db.add(user)
    db.commit()
    return {"msg": "User created"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or user.password != form_data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_hex(16)
    fake_tokens[token] = user.username
    return {"access_token": token, "token_type": "bearer"}

@app.post("/logs")
def create_log(log: LogCreate, db=Depends(get_db), token: Optional[str] = Depends(oauth2_scheme)):
    owner_id = None
    if log.private:
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required for private logs")
        username = fake_tokens.get(token)
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        owner_id = user.id

    expire_at = datetime.utcnow() + timedelta(minutes=log.expire_minutes) if log.expire_minutes else None
    filename = log.filename or f"log_{int(datetime.utcnow().timestamp())}.txt"

    new_log = Log(owner_id=owner_id, filename=filename, content=log.content, private=bool(log.private), expire_at=expire_at)
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    file_path = os.path.join(LOGS_DIR, filename)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(log.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan file: {e}")

    return {
        "message": "Log disimpan!",
        "file_url": f"{BASE_URL}/logs/{filename}",
        "expire_at": expire_at.isoformat() if expire_at else "Tidak ada"
    }

@app.get("/logs", response_model=List[LogOut])
def get_logs(db=Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Log).filter(Log.owner_id == user.id).all()

@app.get("/logs/{log_id}", response_model=LogOut)
def get_log_by_id(log_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    log = db.query(Log).filter(Log.id == log_id, Log.owner_id == user.id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log

@app.delete("/logs/{log_id}")
def delete_log(log_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    log = db.query(Log).filter(Log.id == log_id, Log.owner_id == user.id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    file_path = os.path.join(LOGS_DIR, log.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.delete(log)
    db.commit()
    return {"msg": "Log deleted"}

@app.delete("/autodelete")
def auto_delete_expired(db=Depends(get_db)):
    now = datetime.utcnow()
    deleted = db.query(Log).filter(Log.expire_at != None, Log.expire_at < now).delete()
    db.commit()
    return {"msg": f"{deleted} logs deleted"}

@app.delete("/cleanup")
def cleanup_all_logs(db=Depends(get_db), user: User = Depends(get_current_user)):
    logs = db.query(Log).filter(Log.owner_id == user.id).all()
    for log in logs:
        file_path = os.path.join(LOGS_DIR, log.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    deleted_count = db.query(Log).filter(Log.owner_id == user.id).delete()
    db.commit()
    return {"msg": f"{deleted_count} logs deleted"}
