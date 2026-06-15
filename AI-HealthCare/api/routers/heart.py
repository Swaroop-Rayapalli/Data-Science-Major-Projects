from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import joblib
import pandas as pd
import numpy as np
import os
from api.database import get_db, Prediction

router = APIRouter(prefix="/api/heart", tags=["Heart Disease"])

# Load models safely
MODEL_PATH = os.path.join("trained-models", "heart_disease_random_forest_model.pkl")
SCALER_PATH = os.path.join("trained-models", "heart_disease_scaler.pkl")

try:
    heart_model = joblib.load(MODEL_PATH)
    heart_scaler = joblib.load(SCALER_PATH)
except Exception as e:
    print(f"Warning: Could not load heart models: {e}")
    heart_model, heart_scaler = None, None

class HeartRequest(BaseModel):
    age: float
    sex: float
    cp: float
    trestbps: float
    chol: float
    fbs: float
    restecg: float
    thalach: float
    exang: float
    oldpeak: float
    slope: float
    ca: float
    thal: float

@router.post("/predict")
def predict_heart_disease(data: HeartRequest, db: Session = Depends(get_db)):
    if heart_model is None or heart_scaler is None:
        raise HTTPException(status_code=500, detail="Models not loaded")

    # Order matches the scaler features found earlier
    features = [
        data.age, data.sex, data.cp, data.trestbps, data.chol, 
        data.fbs, data.restecg, data.thalach, data.exang, 
        data.oldpeak, data.slope, data.ca, data.thal
    ]
    
    # Scale features
    features_scaled = heart_scaler.transform([features])
    
    # Predict
    prediction = heart_model.predict(features_scaled)[0]
    probability = heart_model.predict_proba(features_scaled)[0].max() * 100
    
    result_str = "High Risk" if prediction == 1 else "Low Risk"
    
    # Save to DB
    db_pred = Prediction(
        prediction_type="Heart Disease",
        result=f"{result_str} ({probability:.1f}%)"
    )
    db.add(db_pred)
    db.commit()
    db.refresh(db_pred)

    return {
        "risk": result_str,
        "probability": round(probability, 1),
        "prediction_id": db_pred.id
    }
