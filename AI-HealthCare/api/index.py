from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# Serve static files — use __file__ so this works on Vercel (CWD is not project root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

if os.path.isdir(PUBLIC_DIR):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
