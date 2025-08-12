# backend.py
import os
from fastapi import FastAPI, HTTPException, Depends, Response, Request, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import secrets

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)


# ----- Database -----
DATABASE_URL = "sqlite:///./savelog.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# ----- Models -----
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)  # plain untuk demo, sebaiknya pakai hash

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, index=True, nullable=True)  # nullable=True -> anonymous allowed
    filename = Column(String)
    content = Column(Text)
    private = Column(Boolean, default=False)
    expire_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ----- Auth -----
# make token dependency optional (auto_error=False) so we can accept anonymous requests
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)
fake_tokens = {}  # token -> username (simple in-memory token store for demo)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Strict current_user resolver: if token absent or invalid -> raise 401.
    Use this where auth is required.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = fake_tokens.get(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# ----- Schemas -----
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

# ----- App -----
router = APIRouter()

@router.post("/check_missing_files_all")
def check_and_cleanup_missing_files_all(db: Session = Depends(get_db)):
    logs = db.query(Log).all()
    missing_logs = []
    for log in logs:
        file_path = os.path.join(LOGS_DIR, log.filename)
        if not os.path.exists(file_path):
            missing_logs.append(log)

    for log in missing_logs:
        db.delete(log)
    db.commit()

    return {"msg": f"{len(missing_logs)} log(s) removed because file missing"}


app = FastAPI(title="SaveLog Simple API")
app.include_router(router)


app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/logs_public", response_model=List[LogOut])
def get_logs_public(db: Session = Depends(get_db)):
    logs = db.query(Log).filter(Log.private == False).all()
    return logs

@app.get("/logs/{filename}")
async def get_log(filename: str, token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
def register(username: str, password: str, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username exists")
    user = User(username=username, password=password)
    db.add(user)
    db.commit()
    return {"msg": "User created"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Note: OAuth2PasswordRequestForm provides username & password via form-data
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or user.password != form_data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_hex(16)
    fake_tokens[token] = user.username
    return {"access_token": token, "token_type": "bearer"}

@app.post("/logs")
def create_log(
    log: LogCreate,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
):
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

    expire_at = None
    if log.expire_minutes:
        expire_at = datetime.utcnow() + timedelta(minutes=log.expire_minutes)

    filename = log.filename or f"log_{int(datetime.utcnow().timestamp())}.txt"
    new_log = Log(
        owner_id=owner_id,
        filename=filename,
        content=log.content,
        private=bool(log.private),
        expire_at=expire_at
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    # Simpan file fisik
    file_path = os.path.join(LOGS_DIR, filename)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(log.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan file: {e}")

    # URL publik (ganti domain sesuai kebutuhan)
    base_url = "http://localhost:8000/logs"
    file_url = f"{base_url}/{filename}"

    return {
        "message": "Log disimpan!",
        "file_url": file_url,
        "expire_at": expire_at.isoformat() if expire_at else "Tidak ada"
    }



@app.get("/logs", response_model=List[LogOut])
def get_logs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # keep existing behavior: list logs for current authenticated user
    logs = db.query(Log).filter(Log.owner_id == user.id).all()
    return logs

@app.get("/logs/{log_id}", response_model=LogOut)
def get_log(log_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # keep existing behavior: only owner can fetch via this endpoint
    log = db.query(Log).filter(Log.id == log_id, Log.owner_id == user.id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log

@app.delete("/logs/{log_id}")
def delete_log(log_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    log = db.query(Log).filter(Log.id == log_id, Log.owner_id == user.id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    # Hapus file fisik
    file_path = os.path.join(LOGS_DIR, log.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(log)
    db.commit()
    return {"msg": "Log deleted"}


@app.delete("/autodelete")
def auto_delete_expired(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    deleted = db.query(Log).filter(Log.expire_at != None, Log.expire_at < now).delete()
    db.commit()
    return {"msg": f"{deleted} logs deleted"}


@app.delete("/cleanup")
def cleanup_all_logs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Hapus semua log milik user (private dan publik yang dia punya),
    sekaligus hapus file fisiknya.
    """

    # Cari semua log user
    logs = db.query(Log).filter(Log.owner_id == user.id).all()

    # Hapus file fisik setiap log
    for log in logs:
        file_path = os.path.join(LOGS_DIR, log.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    # Hapus record di DB
    deleted_count = db.query(Log).filter(Log.owner_id == user.id).delete()
    db.commit()
    return {"msg": f"{deleted_count} logs deleted"}

