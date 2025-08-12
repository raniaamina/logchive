import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Direktori logs
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Database config
DATABASE_URL = "sqlite:///./logchive.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)  # plaintext untuk demo, sebaiknya hash

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, index=True, nullable=True)  # nullable=True -> anonymous allowed
    filename = Column(String)
    content = Column(Text)
    private = Column(Boolean, default=False)
    expire_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Buat tabel jika belum ada
Base.metadata.create_all(bind=engine)

# Dependency untuk FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
