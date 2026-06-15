import os
from sqlalchemy import create_engine, Column, Integer, String, Numeric, Date, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./healthcare.db")

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"
    patient_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), default="Anonymous")
    age = Column(Integer)
    gender = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=True)
    prediction_type = Column(String(50))
    result = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class FraudClaim(Base):
    __tablename__ = "fraud_claims"
    claim_id = Column(Integer, primary_key=True, index=True)
    claimant_name = Column(String(100), default="Unknown")
    claim_amount = Column(Numeric)
    prediction = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

class MedicineForecast(Base):
    __tablename__ = "medicine_forecasts"
    id = Column(Integer, primary_key=True, index=True)
    medicine_name = Column(String(100))
    predicted_demand = Column(Integer)
    forecast_date = Column(Date)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
