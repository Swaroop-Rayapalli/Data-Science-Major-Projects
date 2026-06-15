from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import joblib
import pandas as pd
import os
from datetime import datetime
from api.database import get_db, MedicineForecast

router = APIRouter(prefix="/api/medicine", tags=["Medicine Forecasting"])

MODEL_PATH = os.path.join("trained-models", "prophet_model.pkl")

try:
    prophet_model = joblib.load(MODEL_PATH)
except Exception as e:
    print(f"Warning: Could not load prophet model: {e}")
    prophet_model = None

class ForecastRequest(BaseModel):
    periods: int
    medicine_name: str
    current_stock: int

@router.post("/forecast")
def generate_forecast(data: ForecastRequest, db: Session = Depends(get_db)):
    if prophet_model is None:
        raise HTTPException(status_code=500, detail="Prophet model not loaded")

    try:
        # Create future dataframe
        future = prophet_model.make_future_dataframe(periods=data.periods)
        forecast = prophet_model.predict(future)
        
        # Get only the forecasted periods (tail)
        future_forecast = forecast.tail(data.periods)[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
        
        # Calculate total predicted demand
        total_predicted_demand = int(future_forecast['yhat'].sum())
        
        # Save each predicted day to DB (optional, or just save the summary)
        # We will save the summary to match the prompt
        db_forecast = MedicineForecast(
            medicine_name=data.medicine_name,
            predicted_demand=total_predicted_demand,
            forecast_date=datetime.utcnow().date()
        )
        db.add(db_forecast)
        db.commit()
        db.refresh(db_forecast)

        # Prepare chart data
        dates = future_forecast['ds'].dt.strftime('%Y-%m-%d').tolist()
        values = future_forecast['yhat'].round(0).astype(int).tolist()
        
        recommendation_qty = max(0, total_predicted_demand - data.current_stock)

        return {
            "medicine_name": data.medicine_name,
            "total_predicted_demand": total_predicted_demand,
            "recommendation": f"Order {recommendation_qty} units." if recommendation_qty > 0 else "Stock is sufficient.",
            "forecast_id": db_forecast.id,
            "chart_data": {
                "dates": dates,
                "values": values
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")
