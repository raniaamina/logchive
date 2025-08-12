import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend import router
from auth import router as auth_router
from config import ALLOWED_ORIGINS, BASE_URL

# === Generate static/config.js dari config.py ===
CONFIG_DICT = {
    "BASE_URL": BASE_URL
}
config_js_content = f"window.APP_CONFIG = {json.dumps(CONFIG_DICT)};\n"

with open("static/config.js", "w", encoding="utf-8") as f:
    f.write(config_js_content)

# === FastAPI app ===
app = FastAPI(title="SaveLog Simple API")

app.include_router(auth_router)
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
