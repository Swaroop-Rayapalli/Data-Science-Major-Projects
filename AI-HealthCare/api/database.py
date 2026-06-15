import os
from sqlalchemy import create_engine, Column, Integer, String, Numeric, Date, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# On Vercel /var/task is read-only — use /tmp for SQLite, or Postgres via env var
_raw_db_url = os.getenv("DATABASE_URL", "")
if not _raw_db_url:
    _sqlite_path = "/tmp/healthcare.db" if os.environ.get("VERCEL") else "./healthcare.db"
    DATABASE_URL = f"sqlite:///{_sqlite_path}"
else:
    DATABASE_URL = _raw_db_url

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

# Create tables — wrapped so an import-time DB error doesn't crash the module
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[DB] Warning: create_all failed: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
