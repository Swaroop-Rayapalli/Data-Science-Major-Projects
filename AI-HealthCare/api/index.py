from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
