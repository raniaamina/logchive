import os

# Port & Host backend
HOST = "localhost"
PORT = 8077

# URL dasar backend
BASE_URL = f"http://{HOST}:{PORT}"

# Folder untuk simpan file log
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# CORS
ALLOWED_ORIGINS = [
    f"http://{HOST}:{PORT}",
    f"http://127.0.0.1:{PORT}",
    f"http://0.0.0.0:{PORT}"
]

# Database URL
DATABASE_URL = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'logs.db')}"
