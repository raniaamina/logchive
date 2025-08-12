from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend import router as backend_router
from auth import router as auth_router

app = FastAPI(title="SaveLog Simple API")

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8077", "http://127.0.0.1:8077", "http://0.0.0.0:8077"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount folder static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register router
app.include_router(auth_router)
app.include_router(backend_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8077, reload=True)
