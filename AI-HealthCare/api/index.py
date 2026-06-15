from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from api.routers import heart, fraud, medicine
import os

app = FastAPI(title="AI Healthcare API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(heart.router)
app.include_router(fraud.router)
app.include_router(medicine.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "AI Healthcare API is running"}

# Build absolute path to public/ relative to this file
# __file__ = /var/task/api/index.py  →  BASE_DIR = /var/task/
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

@app.get("/api/debug-path")
def debug_path():
    """Debug endpoint — shows resolved paths and whether public/ exists."""
    return {
        "__file__":   __file__,
        "BASE_DIR":   BASE_DIR,
        "PUBLIC_DIR": PUBLIC_DIR,
        "public_exists": os.path.isdir(PUBLIC_DIR),
        "public_files":  os.listdir(PUBLIC_DIR) if os.path.isdir(PUBLIC_DIR) else [],
        "cwd": os.getcwd(),
    }

# Explicit root route — returns index.html directly as fallback
@app.get("/")
def serve_root():
    index = os.path.join(PUBLIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index, media_type="text/html")
    return JSONResponse({"error": "index.html not found", "PUBLIC_DIR": PUBLIC_DIR}, status_code=404)

# Mount static files for CSS/JS/other HTML pages
if os.path.isdir(PUBLIC_DIR):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
