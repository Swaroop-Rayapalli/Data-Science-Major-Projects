from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import joblib
import pandas as pd
import numpy as np
import os
from api.database import get_db, FraudClaim

router = APIRouter(prefix="/api/fraud", tags=["Fraud Detection"])

MODEL_PATH = os.path.join("trained-models", "fraud_model.pkl")

try:
    fraud_model = joblib.load(MODEL_PATH)
except Exception as e:
    print(f"Warning: Could not load fraud model: {e}")
    fraud_model = None

class FraudRequest(BaseModel):
    Time: float
    Amount: float
    claimant_name: str
    # Provide defaults for V1-V28 to simplify the UI
    V1: float = 0.0
    V2: float = 0.0
    V3: float = 0.0
    V4: float = 0.0
    V5: float = 0.0
    V6: float = 0.0
    V7: float = 0.0
    V8: float = 0.0
    V9: float = 0.0
    V10: float = 0.0
    V11: float = 0.0
    V12: float = 0.0
    V13: float = 0.0
    V14: float = 0.0
    V15: float = 0.0
    V16: float = 0.0
    V17: float = 0.0
    V18: float = 0.0
    V19: float = 0.0
    V20: float = 0.0
    V21: float = 0.0
    V22: float = 0.0
    V23: float = 0.0
    V24: float = 0.0
    V25: float = 0.0
    V26: float = 0.0
    V27: float = 0.0
    V28: float = 0.0

@router.post("/predict")
def predict_fraud(data: FraudRequest, db: Session = Depends(get_db)):
    if fraud_model is None:
        raise HTTPException(status_code=500, detail="Fraud model not loaded")

    features = [
        data.Time, data.V1, data.V2, data.V3, data.V4, data.V5, data.V6, data.V7,
        data.V8, data.V9, data.V10, data.V11, data.V12, data.V13, data.V14,
        data.V15, data.V16, data.V17, data.V18, data.V19, data.V20, data.V21,
        data.V22, data.V23, data.V24, data.V25, data.V26, data.V27, data.V28, data.Amount
    ]
    
    # Predict using IsolationForest
    # Usually 1 = inlier, -1 = outlier (fraud)
    df = pd.DataFrame([features], columns=['Time', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8', 'V9', 'V10', 'V11', 'V12', 'V13', 'V14', 'V15', 'V16', 'V17', 'V18', 'V19', 'V20', 'V21', 'V22', 'V23', 'V24', 'V25', 'V26', 'V27', 'V28', 'Amount'])
    
    prediction = fraud_model.predict(df)[0]
    
    # Calculate a mock probability or anomaly score
    # If decision_function is available, use it to generate a score
    if hasattr(fraud_model, 'decision_function'):
        score = fraud_model.decision_function(df)[0]
        # normalize to 0-100 roughly
        probability = max(0, min(100, (0.5 - score) * 100))
    else:
        probability = 95.0 if prediction == -1 else 5.0
        
    result_str = "Fraudulent" if prediction == -1 else "Legitimate"

    db_claim = FraudClaim(
        claimant_name=data.claimant_name,
        claim_amount=data.Amount,
        prediction=result_str
    )
    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)

    return {
        "status": result_str,
        "probability": round(probability, 1),
        "claim_id": db_claim.claim_id
    }
