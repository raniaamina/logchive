import os
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import HTTPException, Depends, APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import get_db, Log, LOGS_DIR
from auth import get_current_user, oauth2_scheme

BASE_URL = "http://localhost:8077"

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

router = APIRouter()

@router.get("/")
async def root():
    return FileResponse("static/index.html")

@router.post("/check_missing_files_all")
def check_and_cleanup_missing_files_all(db=Depends(get_db)):
    logs = db.query(Log).all()
    missing_logs = [log for log in logs if not os.path.exists(os.path.join(LOGS_DIR, log.filename))]
    for log in missing_logs:
        db.delete(log)
    db.commit()
    return {"msg": f"{len(missing_logs)} log(s) removed because file missing"}

@router.get("/logs_public", response_model=List[LogOut])
def get_logs_public(db=Depends(get_db)):
    return db.query(Log).filter(Log.private == False).all()

@router.get("/logs/{filename}")
async def get_log(filename: str, token: Optional[str] = Depends(oauth2_scheme), db=Depends(get_db)):
    log = db.query(Log).filter(Log.filename == filename).first()
    if not log:
        raise HTTPException(status_code=404, detail="File not found")

    if log.private:
        from auth import fake_tokens  # hindari circular import
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        username = fake_tokens.get(token)
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(Log.owner.__class__).filter_by(username=username).first()
        if not user or user.id != log.owner_id:
            raise HTTPException(status_code=403, detail="Access denied")

    filepath = os.path.join(LOGS_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)

@router.post("/logs")
def create_log(log: LogCreate, db=Depends(get_db), token: Optional[str] = Depends(oauth2_scheme)):
    from auth import fake_tokens
    owner_id = None
    if log.private:
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required for private logs")
        username = fake_tokens.get(token)
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(Log.owner.__class__).filter_by(username=username).first()
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
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(log.content)

    return {
        "message": "Log disimpan!",
        "file_url": f"{BASE_URL}/logs/{filename}",
        "expire_at": expire_at.isoformat() if expire_at else "Tidak ada"
    }

@router.get("/logs", response_model=List[LogOut])
def get_logs(db=Depends(get_db), user=Depends(get_current_user)):
    return db.query(Log).filter(Log.owner_id == user.id).all()

@router.delete("/autodelete")
def auto_delete_expired(db=Depends(get_db)):
    now = datetime.utcnow()
    deleted = db.query(Log).filter(Log.expire_at != None, Log.expire_at < now).delete()
    db.commit()
    return {"msg": f"{deleted} logs deleted"}

@router.delete("/cleanup")
def cleanup_all_logs(db=Depends(get_db), user=Depends(get_current_user)):
    logs = db.query(Log).filter(Log.owner_id == user.id).all()
    for log in logs:
        file_path = os.path.join(LOGS_DIR, log.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    deleted_count = db.query(Log).filter(Log.owner_id == user.id).delete()
    db.commit()
    return {"msg": f"{deleted_count} logs deleted"}
