import os
import pickle
import joblib
import numpy as np
import pandas as pd
import sqlite3
import traceback
import subprocess
import sys
from flask import Flask, jsonify, request, send_from_directory

# Simple helper to load environment variables from .env file
def load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)  # split only on FIRST = to keep full URL with & params
                    k = k.strip()
                    v = v.strip()
                    if v:  # only set if non-empty
                        os.environ[k] = v

load_dotenv()

app = Flask(__name__, static_folder="static")

# Enable CORS helper
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,Accept"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# Database connection helper (PostgreSQL with SQLite fallback)
pg_conn_pool = None
def get_db_connection():
    db_url = os.environ.get("DATABASE_URL", "")
    
    # Check if a real cloud PostgreSQL database string is configured
    if db_url and "your_supabase_or_neon" not in db_url and db_url.startswith("postgresql://"):
        try:
            import psycopg2
            # Strip channel_binding param — not supported by all psycopg2 builds;
            # sslmode=require alone is sufficient for Neon security.
            clean_url = db_url
            if "channel_binding=require" in clean_url:
                # Remove the param cleanly whether it's first or subsequent
                clean_url = clean_url.replace("&channel_binding=require", "")
                clean_url = clean_url.replace("channel_binding=require&", "")
                clean_url = clean_url.replace("channel_binding=require", "")
                # Clean up any trailing ? or &
                clean_url = clean_url.rstrip("?&")
            conn = psycopg2.connect(clean_url)
            print("Connected to Neon PostgreSQL successfully!")
            return conn, "PostgreSQL"
        except Exception as e:
            print(f"Failed to connect to Neon PostgreSQL, falling back to SQLite. Error: {e}")
            
    # SQLite fallback
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_bi.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, "SQLite"

# Initialize Database tables
def init_db():
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    if db_type == "PostgreSQL":
        # PostgreSQL syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS churn_logs (
                id SERIAL PRIMARY KEY,
                gender VARCHAR(50),
                tenure INTEGER,
                monthly_charges NUMERIC,
                contract VARCHAR(50),
                internet_service VARCHAR(50),
                prediction VARCHAR(50),
                probability NUMERIC,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_logs (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255),
                forecast_sales NUMERIC,
                growth_rate NUMERIC,
                periods INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER,
                products TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_logs (
                id SERIAL PRIMARY KEY,
                area NUMERIC,
                bedrooms INTEGER,
                bathrooms INTEGER,
                location VARCHAR(100),
                price NUMERIC,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    else:
        # SQLite syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS churn_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gender TEXT,
                tenure INTEGER,
                monthly_charges REAL,
                contract TEXT,
                internet_service TEXT,
                prediction TEXT,
                probability REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                forecast_sales REAL,
                growth_rate REAL,
                periods INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                products TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area REAL,
                bedrooms INTEGER,
                bathrooms INTEGER,
                location TEXT,
                price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
    conn.commit()
    conn.close()
    print(f"Database initialized successfully using {db_type}!")

# Try to initialize DB on startup
try:
    init_db()
except Exception as e:
    print(f"Error initializing database: {e}")

# PATHS to Mini-Project Models
MINI_PROJECTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Mini-Projects"))
# Fallback: also check one level up in case directory structure differs
if not os.path.exists(MINI_PROJECTS_DIR):
    MINI_PROJECTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Mini-Projects"))
print(f"Mini-Projects directory: {MINI_PROJECTS_DIR} (exists={os.path.exists(MINI_PROJECTS_DIR)})")

# Load ML Models
models = {
    "churn": None,
    "prophet": None,
    "movies_df": None,
    "similarity": None,
    "house_price": None
}

# Categories ordering matching ChurnModel App
TELCO_CATEGORIES = {
    'gender': ['Female', 'Male'],
    'Partner': ['No', 'Yes'],
    'Dependents': ['No', 'Yes'],
    'PhoneService': ['No', 'Yes'],
    'MultipleLines': ['No', 'No phone service', 'Yes'],
    'InternetService': ['DSL', 'Fiber optic', 'No'],
    'OnlineSecurity': ['No', 'No internet service', 'Yes'],
    'OnlineBackup': ['No', 'No internet service', 'Yes'],
    'DeviceProtection': ['No', 'No internet service', 'Yes'],
    'TechSupport': ['No', 'No internet service', 'Yes'],
    'StreamingTV': ['No', 'No internet service', 'Yes'],
    'StreamingMovies': ['No', 'No internet service', 'Yes'],
    'Contract': ['Month-to-month', 'One year', 'Two year'],
    'PaperlessBilling': ['No', 'Yes'],
    'PaymentMethod': ['Bank transfer (automatic)', 'Credit card (automatic)', 'Electronic check', 'Mailed check']
}


def load_all_models():
    # Churn model
    churn_path = os.path.join(MINI_PROJECTS_DIR, "ChurnModel", "trained-model", "churn_model.pkl")
    if os.path.exists(churn_path):
        try:
            with open(churn_path, "rb") as f:
                models["churn"] = pickle.load(f)
            print("Loaded Customer Churn Model successfully!")
        except Exception as e:
            print(f"Error loading Churn Model: {e}")
            
    # Prophet model
    prophet_path = os.path.join(MINI_PROJECTS_DIR, "SaleForecasting", "trained_model", "prophet_model.pkl")
    if os.path.exists(prophet_path):
        try:
            with open(prophet_path, "rb") as f:
                models["prophet"] = pickle.load(f)
            print("Loaded Sales Forecasting Prophet Model successfully!")
        except Exception as e:
            print(f"Error loading Prophet Model: {e}")
            
    # Recommendation files
    rec_movies_path = os.path.join(MINI_PROJECTS_DIR, "MovieRecommendition", "trained-model", "movies.pkl")
    rec_sim_path = os.path.join(MINI_PROJECTS_DIR, "MovieRecommendition", "trained-model", "similarity.pkl")
    if os.path.exists(rec_movies_path) and os.path.exists(rec_sim_path):
        try:
            with open(rec_movies_path, "rb") as f:
                models["movies_df"] = pickle.load(f)
            print("Loaded Recommendation Movie Dataset successfully!")
            
            # Since similarity is 750MB, let's load it lazily or at start.
            # We will load it here, but wrap in try-catch in case of memory limits.
            print("Loading 759MB Recommendation similarity matrix...")
            with open(rec_sim_path, "rb") as f:
                models["similarity"] = pickle.load(f)
            print("Loaded Recommendation similarity matrix successfully!")
        except Exception as e:
            print(f"Error loading Recommendation Models: {e}")
            
    # House price model
    house_path = os.path.join(MINI_PROJECTS_DIR, "HousePricePred", "house_price_model.pkl")
    if os.path.exists(house_path):
        try:
            models["house_price"] = joblib.load(house_path)
            print("Loaded House Price Prediction Model successfully!")
        except Exception as e:
            print(f"Error loading House Price Model: {e}")

# Load models on server boot
load_all_models()

# Endpoints

@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

@app.route("/api/config", methods=["GET"])
def get_config():
    """Return Power BI URL and check if cloud Postgres is connected."""
    db_url = os.environ.get("DATABASE_URL", "")
    has_postgres = db_url and "your_supabase_or_neon" not in db_url and db_url.startswith("postgresql://")
    pbi_url = os.environ.get("POWERBI_EMBED_URL", "")
    
    # Hide password in connection string if returning it
    masked_db = "PostgreSQL Connected" if has_postgres else "SQLite (Local File)"
    
    return jsonify({
        "db_status": masked_db,
        "powerbi_url": pbi_url if pbi_url and "eyJrIjoi" not in pbi_url else ""
    })

# 1. Customer Churn API
@app.route("/predict", methods=["POST"])
@app.route("/api/predict-churn", methods=["POST"])
def predict_churn():
    if models["churn"] is None:
        return jsonify({"success": False, "error": "Churn model is not loaded on server."}), 500
        
    try:
        data = request.get_json() or {}
        
        # Extracted parameters mapping
        gender = data.get("gender", "Female")
        tenure = int(data.get("tenure", 12))
        monthly_charges = float(data.get("MonthlyCharges", 80.0))
        contract = data.get("Contract", "Month-to-month")
        internet_service = data.get("InternetService", "Fiber optic")
        
        # Prepare full feature record with standard defaults matching Telco dataset
        row = {
            'gender': gender,
            'SeniorCitizen': int(data.get("SeniorCitizen", 0)),
            'Partner': data.get('Partner', 'No'),
            'Dependents': data.get('Dependents', 'No'),
            'tenure': tenure,
            'PhoneService': data.get('PhoneService', 'Yes'),
            'MultipleLines': data.get('MultipleLines', 'No'),
            'InternetService': internet_service,
            'OnlineSecurity': data.get('OnlineSecurity', 'No'),
            'OnlineBackup': data.get('OnlineBackup', 'No'),
            'DeviceProtection': data.get('DeviceProtection', 'No'),
            'TechSupport': data.get('TechSupport', 'No'),
            'StreamingTV': data.get('StreamingTV', 'No'),
            'StreamingMovies': data.get('StreamingMovies', 'No'),
            'Contract': contract,
            'PaperlessBilling': data.get('PaperlessBilling', 'Yes'),
            'PaymentMethod': data.get('PaymentMethod', 'Electronic check'),
            'MonthlyCharges': monthly_charges,
            'TotalCharges': float(data.get("TotalCharges", monthly_charges * tenure))
        }
        
        # Convert to DataFrame
        df = pd.DataFrame([row])
        
        # Categorical formatting
        for col, categories in TELCO_CATEGORIES.items():
            val = df.at[0, col]
            if val not in categories:
                matches = [c for c in categories if c.lower() == str(val).lower()]
                df.at[0, col] = matches[0] if matches else categories[0]
            df[col] = pd.Categorical(df[col], categories=categories)
            
        columns_expected = [
            'gender', 'SeniorCitizen', 'Partner', 'Dependents', 'tenure', 'PhoneService',
            'MultipleLines', 'InternetService', 'OnlineSecurity', 'OnlineBackup',
            'DeviceProtection', 'TechSupport', 'StreamingTV', 'StreamingMovies',
            'Contract', 'PaperlessBilling', 'PaymentMethod', 'MonthlyCharges', 'TotalCharges'
        ]
        df = df[columns_expected]
        
        # Predict
        prob = float(models["churn"].predict_proba(df)[0][1])
        prediction_label = "Churn" if prob >= 0.5 else "No Churn"
        
        # SAVE TO DATABASE
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == "PostgreSQL":
            cursor.execute("""
                INSERT INTO churn_logs (gender, tenure, monthly_charges, contract, internet_service, prediction, probability)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (gender, tenure, monthly_charges, contract, internet_service, prediction_label, prob))
        else:
            cursor.execute("""
                INSERT INTO churn_logs (gender, tenure, monthly_charges, contract, internet_service, prediction, probability)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (gender, tenure, monthly_charges, contract, internet_service, prediction_label, prob))
        conn.commit()
        conn.close()
        
        return jsonify({
            "prediction": prediction_label,
            "probability": round(prob, 2)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# 2. Sales Forecasting API
@app.route("/api/forecast", methods=["POST"])
def forecast_sales():
    if models["prophet"] is None:
        return jsonify({"success": False, "error": "Prophet model not loaded on server."}), 500
        
    try:
        # Accept JSON (no-file path) or multipart form (file upload path)
        file = request.files.get("file")
        if request.is_json:
            body   = request.get_json() or {}
            periods = int(body.get("periods", 90))
        else:
            periods = int(request.form.get("periods", 90))
        filename = "Manual Request"
        
        # Default values
        growth_rate = 0.0
        
        # If file provided, we read it
        if file and file.filename != '':
            filename = file.filename
            try:
                df_csv = pd.read_csv(file)
                cols_lower = {c.lower().strip(): c for c in df_csv.columns}
                
                # ── Auto-detect DATE column ──────────────────────────────────
                DATE_ALIASES = ['ds','date','order_date','order date','timestamp',
                                'time','week','month','day','created_at','invoice_date',
                                'sale_date','transaction_date','period','report_date']
                date_col = None
                for alias in DATE_ALIASES:
                    if alias in cols_lower:
                        date_col = cols_lower[alias]
                        break
                # Fallback: first column that looks like a date
                if date_col is None:
                    for c in df_csv.columns:
                        try:
                            pd.to_datetime(df_csv[c].dropna().head(5))
                            date_col = c
                            break
                        except Exception:
                            pass
                
                # ── Auto-detect SALES/VALUE column ───────────────────────────
                VALUE_ALIASES = ['y','sales','revenue','amount','total','total_sales',
                                 'value','quantity','qty','orders','transactions',
                                 'income','profit','gross_sales','net_sales','price',
                                 'turnover','units_sold']
                val_col = None
                for alias in VALUE_ALIASES:
                    if alias in cols_lower:
                        val_col = cols_lower[alias]
                        break
                # Fallback: first numeric column that is not the date column
                if val_col is None:
                    for c in df_csv.select_dtypes(include='number').columns:
                        if c != date_col:
                            val_col = c
                            break
                
                if date_col is None or val_col is None:
                    raise ValueError(
                        f"Could not detect date or value column. "
                        f"Found columns: {list(df_csv.columns)}. "
                        f"Please ensure your CSV has a date column and a numeric sales/revenue column."
                    )
                
                # Rename to Prophet-expected ds / y
                df_csv = df_csv[[date_col, val_col]].rename(columns={date_col: 'ds', val_col: 'y'})
                df_csv['ds'] = pd.to_datetime(df_csv['ds'])
                df_csv['y']  = pd.to_numeric(df_csv['y'], errors='coerce')
                df_csv = df_csv.dropna()
                
                print(f"[Forecast] CSV mapped: '{date_col}' → ds, '{val_col}' → y  ({len(df_csv)} rows)")
                max_date  = df_csv['ds'].max()
                last_sales = float(df_csv['y'].tail(periods).sum() if len(df_csv) >= periods else df_csv['y'].sum())
                
            except Exception as parse_err:
                return jsonify({"success": False, "error": str(parse_err)}), 400
        else:
            # No file — use historical Prophet model training data
            history = models["prophet"].history
            max_date   = history['ds'].max()
            last_sales = float(history['y'].tail(periods).sum() if len(history) >= periods else history['y'].sum())


        # Run Prophet predictions
        future = models["prophet"].make_future_dataframe(periods=periods, freq='D')
        forecast = models["prophet"].predict(future)
        
        # Filter future only
        forecast_only = forecast[forecast['ds'] > max_date].copy()
        
        # Scale predictions to total sales using day-of-week transaction multipliers
        # Similar logic as in SaleForecasting app.py
        forecast_only['day_of_week'] = forecast_only['ds'].dt.dayofweek
        # Mocking average daily transaction count
        forecast_only['orders'] = forecast_only['day_of_week'].map(lambda x: 8.0)
        forecast_only['sales'] = forecast_only['yhat'] * forecast_only['orders']
        
        # Prepare response list as [{ds, sales, yhat}] objects for the chart
        forecast_records = []
        for _, row in forecast_only.iterrows():
            forecast_records.append({
                "ds":    row["ds"].strftime("%Y-%m-%d"),
                "sales": round(float(row["sales"]), 2),
                "yhat":  round(float(row["yhat"]), 2)
            })
        
        total_forecast = float(sum(r["sales"] for r in forecast_records))
        
        # Growth Rate calculation
        if last_sales > 0:
            growth_rate = round(float(((total_forecast - float(last_sales)) / float(last_sales)) * 100), 2)
            
        # SAVE TO DATABASE
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == "PostgreSQL":
            cursor.execute("""
                INSERT INTO sales_logs (filename, forecast_sales, growth_rate, periods)
                VALUES (%s, %s, %s, %s)
            """, (filename, total_forecast, growth_rate, periods))
        else:
            cursor.execute("""
                INSERT INTO sales_logs (filename, forecast_sales, growth_rate, periods)
                VALUES (?, ?, ?, ?)
            """, (filename, total_forecast, growth_rate, periods))
        conn.commit()
        conn.close()
        
        return jsonify({
            "forecast": forecast_records,
            "summary": {
                "total_sales": round(total_forecast, 2),
                "growth_rate_pct": growth_rate,
                "periods": periods
            }
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# 3. Product Recommendation Engine API
@app.route("/api/recommend", methods=["POST"])
def get_recommendations():
    if models["movies_df"] is None or models["similarity"] is None:
        # Fallback recommendations if models failed to load
        fallback_recs = ["The Dark Knight", "Inception", "Interstellar", "The Matrix", "Pulp Fiction"]
        return jsonify({
            "recommendations": fallback_recs,
            "seed_movie": "Popular Picks",
            "message": "Model not loaded. Returning popular movies."
        })
        
    try:
        data = request.get_json() or {}
        
        # Feature-based inputs from user
        genre    = data.get("genre", "Action")      # e.g. Action, Comedy, Drama, Horror
        mood     = data.get("mood", "exciting")     # exciting, feel-good, emotional, scary, thoughtful
        era      = data.get("era", "modern")        # classic, 90s, 2000s, modern
        language = data.get("language", "english").lower()  # english, hindi, korean, etc.
        
        # ── NON-ENGLISH: curated real films per language ──────────────────────────
        NON_ENGLISH_FILMS = {
            "hindi": {
                "Action":      [{"title":"War (2019)","genre":"Action","score":97.0},{"title":"Pathaan (2023)","genre":"Action","score":95.0},{"title":"Baahubali: The Beginning (2015)","genre":"Action","score":93.5},{"title":"Dhoom 3 (2013)","genre":"Action/Thriller","score":91.0},{"title":"Tiger Zinda Hai (2017)","genre":"Action","score":89.5}],
                "Comedy":      [{"title":"3 Idiots (2009)","genre":"Comedy/Drama","score":98.0},{"title":"Andaz Apna Apna (1994)","genre":"Comedy","score":96.5},{"title":"Hera Pheri (2000)","genre":"Comedy","score":95.0},{"title":"Munna Bhai M.B.B.S. (2003)","genre":"Comedy/Drama","score":93.0},{"title":"Golmaal (2006)","genre":"Comedy","score":91.0}],
                "Drama":       [{"title":"Taare Zameen Par (2007)","genre":"Drama","score":98.5},{"title":"Dil Dhadakne Do (2015)","genre":"Drama","score":95.0},{"title":"Kapoor & Sons (2016)","genre":"Drama","score":93.5},{"title":"Pink (2016)","genre":"Drama/Thriller","score":96.0},{"title":"Kahaani (2012)","genre":"Drama/Thriller","score":94.0}],
                "Romance":     [{"title":"Dilwale Dulhania Le Jayenge (1995)","genre":"Romance","score":99.0},{"title":"Jab We Met (2007)","genre":"Romance/Comedy","score":97.0},{"title":"Kal Ho Naa Ho (2003)","genre":"Romance/Drama","score":95.5},{"title":"Rockstar (2011)","genre":"Romance/Drama","score":93.0},{"title":"Ae Dil Hai Mushkil (2016)","genre":"Romance","score":91.5}],
                "Thriller":    [{"title":"Andhadhun (2018)","genre":"Thriller","score":98.5},{"title":"Drishyam (2015)","genre":"Thriller","score":97.0},{"title":"Article 15 (2019)","genre":"Thriller/Drama","score":95.5},{"title":"A Wednesday (2008)","genre":"Thriller","score":96.0},{"title":"Special 26 (2013)","genre":"Thriller","score":93.5}],
                "Horror":      [{"title":"Stree (2018)","genre":"Horror/Comedy","score":96.5},{"title":"Tumbbad (2018)","genre":"Horror","score":98.0},{"title":"Bhoot (2003)","genre":"Horror","score":91.0},{"title":"Raaz (2002)","genre":"Horror/Romance","score":89.5},{"title":"Go Goa Gone (2013)","genre":"Horror/Comedy","score":88.0}],
                "default":     [{"title":"3 Idiots (2009)","genre":"Comedy/Drama","score":98.0},{"title":"Dangal (2016)","genre":"Drama/Sport","score":97.5},{"title":"Andhadhun (2018)","genre":"Thriller","score":98.5},{"title":"Taare Zameen Par (2007)","genre":"Drama","score":98.5},{"title":"PK (2014)","genre":"Comedy/Drama","score":96.5}],
            },
            "telugu": {
                "Action":      [{"title":"Baahubali: The Beginning (2015)","genre":"Action/Epic","score":99.0},{"title":"Baahubali 2: The Conclusion (2017)","genre":"Action/Epic","score":98.5},{"title":"RRR (2022)","genre":"Action/Drama","score":98.0},{"title":"Pushpa: The Rise (2021)","genre":"Action/Thriller","score":96.5},{"title":"Saaho (2019)","genre":"Action/Thriller","score":91.0}],
                "Drama":       [{"title":"Mahanati (2018)","genre":"Drama/Biography","score":98.5},{"title":"Jersey (2019)","genre":"Drama/Sport","score":97.5},{"title":"Arjun Reddy (2017)","genre":"Drama/Romance","score":96.5},{"title":"Fidaa (2017)","genre":"Drama/Romance","score":95.0},{"title":"96 (Tamil/Telugu) (2018)","genre":"Drama/Romance","score":97.0}],
                "Romance":     [{"title":"Geetha Govindam (2018)","genre":"Romance/Comedy","score":97.0},{"title":"Fidaa (2017)","genre":"Romance/Drama","score":96.0},{"title":"Arjun Reddy (2017)","genre":"Romance/Drama","score":96.5},{"title":"Ye Maaya Chesave (2010)","genre":"Romance","score":95.5},{"title":"Bommarillu (2006)","genre":"Romance/Comedy","score":95.0}],
                "Thriller":    [{"title":"Kshanam (2016)","genre":"Thriller","score":97.5},{"title":"Agent Sai Srinivasa Athreya (2019)","genre":"Thriller/Comedy","score":96.0},{"title":"Goodachari (2018)","genre":"Spy/Thriller","score":95.5},{"title":"Evaru (2019)","genre":"Thriller","score":96.5},{"title":"Vakeel Saab (2021)","genre":"Drama/Thriller","score":94.5}],
                "Comedy":      [{"title":"Golmaal (Telugu) (2010)","genre":"Comedy","score":93.0},{"title":"Dookudu (2011)","genre":"Action/Comedy","score":94.5},{"title":"Julayi (2012)","genre":"Comedy/Action","score":93.5},{"title":"Attarintiki Daredi (2013)","genre":"Comedy/Drama","score":95.0},{"title":"Ala Vaikunthapurramuloo (2020)","genre":"Comedy/Action","score":96.5}],
                "Horror":      [{"title":"Arundhati (2009)","genre":"Horror/Action","score":96.0},{"title":"Anando Brahma (2017)","genre":"Horror/Comedy","score":93.5},{"title":"Bhaagamathie (2018)","genre":"Horror/Thriller","score":95.0},{"title":"Gruham (2017)","genre":"Horror/Thriller","score":94.0},{"title":"Devi (2016)","genre":"Horror/Comedy","score":92.5}],
                "Animation":   [{"title":"Arjuna: The Warrior Prince (2012)","genre":"Animation/Action","score":91.0},{"title":"Hanuman (2005)","genre":"Animation/Adventure","score":94.0},{"title":"Super Krishna (2018)","genre":"Animation/Adventure","score":89.5},{"title":"Bal Ganesh (2007)","genre":"Animation","score":88.5},{"title":"Little Krishna (2009)","genre":"Animation","score":90.0}],
                "default":     [{"title":"Baahubali 2: The Conclusion (2017)","genre":"Action/Epic","score":98.5},{"title":"RRR (2022)","genre":"Action/Drama","score":98.0},{"title":"Mahanati (2018)","genre":"Drama/Biography","score":98.5},{"title":"Kshanam (2016)","genre":"Thriller","score":97.5},{"title":"Arjun Reddy (2017)","genre":"Drama/Romance","score":96.5}],
            },
            "korean": {
                "Thriller":    [{"title":"Parasite (2019)","genre":"Thriller/Drama","score":99.0},{"title":"Oldboy (2003)","genre":"Thriller","score":98.0},{"title":"I Saw the Devil (2010)","genre":"Thriller","score":96.5},{"title":"A Bittersweet Life (2005)","genre":"Thriller","score":94.5},{"title":"The Wailing (2016)","genre":"Thriller/Horror","score":95.5}],
                "Romance":     [{"title":"My Sassy Girl (2001)","genre":"Romance/Comedy","score":97.0},{"title":"A Moment to Remember (2004)","genre":"Romance/Drama","score":96.0},{"title":"The Classic (2003)","genre":"Romance","score":94.5},{"title":"Architecture 101 (2012)","genre":"Romance","score":93.0},{"title":"Il Mare (2000)","genre":"Romance","score":95.0}],
                "Horror":      [{"title":"Train to Busan (2016)","genre":"Horror/Action","score":98.5},{"title":"The Wailing (2016)","genre":"Horror","score":96.5},{"title":"A Tale of Two Sisters (2003)","genre":"Horror","score":97.0},{"title":"Thirst (2009)","genre":"Horror","score":94.5},{"title":"The Host (2006)","genre":"Horror/Action","score":96.0}],
                "Drama":       [{"title":"Oasis (2002)","genre":"Drama","score":97.5},{"title":"Poetry (2010)","genre":"Drama","score":96.0},{"title":"Secret Sunshine (2007)","genre":"Drama","score":95.5},{"title":"A Taxi Driver (2017)","genre":"Drama","score":96.5},{"title":"1987: When the Day Comes (2017)","genre":"Drama","score":95.0}],
                "default":     [{"title":"Parasite (2019)","genre":"Drama/Thriller","score":99.0},{"title":"Train to Busan (2016)","genre":"Horror/Action","score":98.5},{"title":"Oldboy (2003)","genre":"Thriller","score":98.0},{"title":"Burning (2018)","genre":"Drama","score":96.5},{"title":"The Handmaiden (2016)","genre":"Drama/Thriller","score":97.5}],
            },
            "japanese": {
                "Animation":   [{"title":"Spirited Away (2001)","genre":"Animation","score":99.0},{"title":"My Neighbor Totoro (1988)","genre":"Animation","score":98.5},{"title":"Princess Mononoke (1997)","genre":"Animation/Adventure","score":98.0},{"title":"Howl's Moving Castle (2004)","genre":"Animation","score":97.0},{"title":"Akira (1988)","genre":"Animation/Sci-Fi","score":97.5}],
                "Drama":       [{"title":"Shoplifters (2018)","genre":"Drama","score":98.0},{"title":"Still Walking (2008)","genre":"Drama","score":96.5},{"title":"After Life (1998)","genre":"Drama","score":97.0},{"title":"Nobody Knows (2004)","genre":"Drama","score":96.0},{"title":"Departures (2008)","genre":"Drama","score":97.5}],
                "Horror":      [{"title":"Ringu (1998)","genre":"Horror","score":97.0},{"title":"Ju-On: The Grudge (2002)","genre":"Horror","score":95.5},{"title":"Audition (1999)","genre":"Horror/Thriller","score":96.5},{"title":"Dark Water (2002)","genre":"Horror","score":94.0},{"title":"Pulse (2001)","genre":"Horror","score":93.5}],
                "default":     [{"title":"Spirited Away (2001)","genre":"Animation","score":99.0},{"title":"Parasite (2003) - Note: see Korean","genre":"Drama","score":98.0},{"title":"Shoplifters (2018)","genre":"Drama","score":98.0},{"title":"Princess Mononoke (1997)","genre":"Animation","score":98.0},{"title":"Ringu (1998)","genre":"Horror","score":97.0}],
            },
            "french": {
                "Romance":     [{"title":"Amélie (2001)","genre":"Romance/Comedy","score":99.0},{"title":"Blue Is the Warmest Colour (2013)","genre":"Romance/Drama","score":96.5},{"title":"The Artist (2011)","genre":"Romance/Drama","score":97.0},{"title":"Lola (1961)","genre":"Romance","score":95.0},{"title":"Cache (2005)","genre":"Drama/Thriller","score":95.5}],
                "Thriller":    [{"title":"Tell No One (2006)","genre":"Thriller","score":97.0},{"title":"Cache (2005)","genre":"Thriller/Drama","score":96.0},{"title":"The Connection (2014)","genre":"Crime/Thriller","score":94.5},{"title":"A Prophet (2009)","genre":"Crime/Drama","score":97.5},{"title":"Leon: The Professional (1994)","genre":"Action/Thriller","score":98.0}],
                "default":     [{"title":"Amélie (2001)","genre":"Romance/Comedy","score":99.0},{"title":"Leon: The Professional (1994)","genre":"Action/Thriller","score":98.0},{"title":"A Prophet (2009)","genre":"Crime/Drama","score":97.5},{"title":"The Artist (2011)","genre":"Drama","score":97.0},{"title":"Tell No One (2006)","genre":"Thriller","score":97.0}],
            },
            "spanish": {
                "Thriller":    [{"title":"The Invisible Guest (2016)","genre":"Thriller","score":98.0},{"title":"The Body (2012)","genre":"Thriller","score":96.0},{"title":"Sleep Tight (2011)","genre":"Thriller/Horror","score":95.5},{"title":"Cell 211 (2009)","genre":"Thriller","score":97.0},{"title":"The Method (2005)","genre":"Thriller/Drama","score":94.5}],
                "Horror":      [{"title":"REC (2007)","genre":"Horror","score":97.5},{"title":"The Orphanage (2007)","genre":"Horror/Drama","score":97.0},{"title":"Pan's Labyrinth (2006)","genre":"Fantasy/Horror","score":98.5},{"title":"Sleep Tight (2011)","genre":"Horror/Thriller","score":95.5},{"title":"[REC]2 (2009)","genre":"Horror","score":93.5}],
                "default":     [{"title":"Pan's Labyrinth (2006)","genre":"Fantasy/Horror","score":98.5},{"title":"The Invisible Guest (2016)","genre":"Thriller","score":98.0},{"title":"REC (2007)","genre":"Horror","score":97.5},{"title":"The Orphanage (2007)","genre":"Horror/Drama","score":97.0},{"title":"Cell 211 (2009)","genre":"Thriller","score":97.0}],
            },
            "german": {
                "Drama":       [{"title":"The Lives of Others (2006)","genre":"Drama/Thriller","score":98.5},{"title":"Downfall (2004)","genre":"Drama/History","score":97.5},{"title":"Goodbye Lenin! (2003)","genre":"Drama/Comedy","score":96.5},{"title":"Run Lola Run (1998)","genre":"Thriller/Action","score":97.0},{"title":"The White Ribbon (2009)","genre":"Drama","score":96.0}],
                "default":     [{"title":"The Lives of Others (2006)","genre":"Drama/Thriller","score":98.5},{"title":"Run Lola Run (1998)","genre":"Thriller","score":97.0},{"title":"Downfall (2004)","genre":"Drama","score":97.5},{"title":"Goodbye Lenin! (2003)","genre":"Comedy/Drama","score":96.5},{"title":"The White Ribbon (2009)","genre":"Drama","score":96.0}],
            },
            "italian": {
                "Drama":       [{"title":"Cinema Paradiso (1988)","genre":"Drama","score":99.0},{"title":"Life Is Beautiful (1997)","genre":"Drama/Comedy","score":98.5},{"title":"The Great Beauty (2013)","genre":"Drama","score":97.0},{"title":"Bicycle Thieves (1948)","genre":"Drama","score":98.0},{"title":"Il Divo (2008)","genre":"Drama/Biography","score":95.5}],
                "default":     [{"title":"Cinema Paradiso (1988)","genre":"Drama","score":99.0},{"title":"Life Is Beautiful (1997)","genre":"Drama/Comedy","score":98.5},{"title":"Bicycle Thieves (1948)","genre":"Drama","score":98.0},{"title":"The Great Beauty (2013)","genre":"Drama","score":97.0},{"title":"Il Postino (1994)","genre":"Drama/Romance","score":96.5}],
            },
        }
        
        # If non-English, return curated list (ML model is English-only)
        if language != "english" and language in NON_ENGLISH_FILMS:
            lang_db = NON_ENGLISH_FILMS[language]
            recs = lang_db.get(genre, lang_db.get("default", []))
            # Filter by era loosely via year in title
            import re as _re2
            def get_year(t):
                m = _re2.search(r'\((\d{4})\)', str(t))
                return int(m.group(1)) if m else 2000
            ERA_RANGE2 = {"classic":(1900,1989),"90s":(1990,1999),"2000s":(2000,2009),"modern":(2010,2030)}
            yr_min2, yr_max2 = ERA_RANGE2.get(era, (1900, 2030))
            era_filtered = [r for r in recs if yr_min2 <= get_year(r["title"]) <= yr_max2]
            final_recs = era_filtered if len(era_filtered) >= 2 else recs
            seed_title = f"Top {language.capitalize()} {genre} Films"
            
            # Save to DB
            conn, db_type = get_db_connection()
            cursor = conn.cursor()
            titles_str = ", ".join(r["title"] for r in final_recs[:5])
            if db_type == "PostgreSQL":
                cursor.execute("INSERT INTO recommendations (customer_id, products) VALUES (%s, %s)", (0, titles_str))
            else:
                cursor.execute("INSERT INTO recommendations (customer_id, products) VALUES (?, ?)", (0, titles_str))
            conn.commit()
            conn.close()
            
            return jsonify({"recommendations": final_recs[:5], "seed_movie": seed_title, "genre": genre, "mood": mood, "era": era, "language": language})


        
        # Map mood -> genre hint to help narrow search
        MOOD_GENRE_MAP = {
            "exciting":    ["Action", "Adventure", "Thriller"],
            "feel-good":   ["Comedy", "Animation", "Musical", "Romance"],
            "emotional":   ["Drama", "Romance", "War"],
            "scary":       ["Horror", "Thriller", "Mystery"],
            "thoughtful":  ["Sci-Fi", "Drama", "Documentary", "Mystery"],
        }
        ERA_RANGE = {
            "classic": (1900, 1989),
            "90s":     (1990, 1999),
            "2000s":   (2000, 2009),
            "modern":  (2010, 2030),
        }
        
        movies_df = models["movies_df"]
        
        # Filter by ERA using year in title "(YYYY)"
        import re as _re
        def extract_year(title):
            m = _re.search(r'\((\d{4})\)', str(title))
            return int(m.group(1)) if m else 2000
        
        yr_min, yr_max = ERA_RANGE.get(era, (1900, 2030))
        era_mask = movies_df['title'].apply(lambda t: yr_min <= extract_year(t) <= yr_max)
        
        # Filter by primary genre
        genre_mask = movies_df['genres'].str.contains(genre, case=False, na=False)
        
        # Combine filters: genre + era preferred, fall back to genre-only
        filtered = movies_df[genre_mask & era_mask]
        if len(filtered) < 3:
            filtered = movies_df[genre_mask]
        if len(filtered) < 3:
            filtered = movies_df  # final fallback
        
        # Also try mood secondary genres as bonus filter
        mood_genres = MOOD_GENRE_MAP.get(mood, [genre])
        mood_mask = movies_df['genres'].apply(
            lambda g: any(mg.lower() in str(g).lower() for mg in mood_genres)
        )
        mood_filtered = movies_df[mood_mask & era_mask]
        if len(mood_filtered) >= 3:
            filtered = mood_filtered
        
        # Pick a seed movie (deterministic, middle of filtered set for variety)
        seed_row = filtered.iloc[len(filtered) // 3]
        seed_title = str(seed_row.get('title', seed_row.iloc[1]))
        movie_idx = filtered.index[len(filtered) // 3]
        
        # Clamp index to similarity matrix size
        sim_size = len(models["similarity"])
        movie_idx = min(int(movie_idx), sim_size - 1)
        
        # Run similarity search
        distances = models["similarity"][movie_idx]
        raw_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])
        
        # Get top 5 recommendations (excluding seed itself)
        recommended_indices = []
        for idx, score in raw_list:
            if idx == movie_idx:
                continue
            recommended_indices.append(idx)
            if len(recommended_indices) >= 5:
                break
        
        # Fetch actual movie titles
        recs = []
        scores = []
        for i, idx in enumerate(recommended_indices):
            clamped = min(idx, len(movies_df) - 1)
            row = movies_df.iloc[clamped]
            title = str(row.get('title', row.iloc[1]))
            genre_tag = str(row.get('genres', '')).split('|')[0]
            recs.append({"title": title, "genre": genre_tag, "score": round(raw_list[i+1][1] * 100, 1)})
        
        if not recs:
            recs = [
                {"title": "The Dark Knight", "genre": "Action", "score": 97.0},
                {"title": "Inception", "genre": "Sci-Fi", "score": 95.5},
                {"title": "Interstellar", "genre": "Sci-Fi", "score": 93.0},
            ]
        
        # SAVE TO DATABASE
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        titles_str = ", ".join(r["title"] for r in recs)
        if db_type == "PostgreSQL":
            cursor.execute("""
                INSERT INTO recommendations (customer_id, products)
                VALUES (%s, %s)
            """, (0, titles_str))
        else:
            cursor.execute("""
                INSERT INTO recommendations (customer_id, products)
                VALUES (?, ?)
            """, (0, titles_str))
        conn.commit()
        conn.close()
        
        return jsonify({
            "recommendations": recs,
            "seed_movie": seed_title,
            "genre": genre,
            "mood": mood,
            "era": era
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# 4. Property Price API
@app.route("/api/predict-price", methods=["POST"])
def predict_price():
    if models["house_price"] is None:
        return jsonify({"success": False, "error": "House price model not loaded on server."}), 500
        
    try:
        data = request.get_json() or {}
        
        area = float(data.get("area", 1500))
        bedrooms = int(data.get("bedrooms", 3))
        bathrooms = int(data.get("bathrooms", 2))
        location = data.get("location", "medium").lower()
        
        # Map location string to integer label-encoded values
        # New 2025 model: low=0, medium=1, premium=2
        # Income level:   high=0, low=1, mid=2, very_low=3
        loc_lower = location.lower()
        if loc_lower == "premium" or loc_lower == "high":
            location_val = 2
            income_level_val = 0   # high income (premium area)
        elif loc_lower == "medium" or loc_lower == "suburban":
            location_val = 1
            income_level_val = 2   # mid income
        else:  # low / budget / any other
            location_val = 0
            income_level_val = 1   # low income
            
        # Construct row with the full 18 features (using user inputs + dataset defaults from HousePricePred/app.py)
        DEFAULTS = {
            'floors': 2.0,
            'age': 20.0,
            'distance': 15.0,
            'garage': 1.0,
            'parking': 0.0,
            'garden': 1.0,
            'security': 0.0,
            'school_nearby': 1.0,
            'hospital_nearby': 0.0,
            'shopping_mall_nearby': 0.0,
            'public_transport': 1.0,
            'crime_rate': 5.022946110697763,
            'population_density': 5060.5,
            'location': location_val,
            'income_level': income_level_val
        }
        
        FEATURE_NAMES = [
            'area', 'bedrooms', 'bathrooms', 'floors', 'age', 'distance',
            'garage', 'parking', 'garden', 'security', 'school_nearby',
            'hospital_nearby', 'shopping_mall_nearby', 'public_transport',
            'crime_rate', 'population_density', 'location', 'income_level'
        ]
        
        feature_values = [[
            area, bedrooms, bathrooms,
            DEFAULTS['floors'], DEFAULTS['age'], DEFAULTS['distance'],
            DEFAULTS['garage'], DEFAULTS['parking'], DEFAULTS['garden'],
            DEFAULTS['security'], DEFAULTS['school_nearby'], DEFAULTS['hospital_nearby'],
            DEFAULTS['shopping_mall_nearby'], DEFAULTS['public_transport'],
            DEFAULTS['crime_rate'], DEFAULTS['population_density'],
            DEFAULTS['location'], DEFAULTS['income_level']
        ]]
        
        # Convert to DataFrame
        X_pred = pd.DataFrame(feature_values, columns=FEATURE_NAMES)
        
        # Predict price
        price = float(models["house_price"].predict(X_pred)[0])
        
        # SAVE TO DATABASE
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == "PostgreSQL":
            cursor.execute("""
                INSERT INTO property_logs (area, bedrooms, bathrooms, location, price)
                VALUES (%s, %s, %s, %s, %s)
            """, (area, bedrooms, bathrooms, location, price))
        else:
            cursor.execute("""
                INSERT INTO property_logs (area, bedrooms, bathrooms, location, price)
                VALUES (?, ?, ?, ?, ?)
            """, (area, bedrooms, bathrooms, location, price))
        conn.commit()
        conn.close()
        
        # Return format matching Step 6
        return jsonify({
            "price": round(price, 2)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400

# 5. Dashboard Stats API
@app.route("/api/dashboard-stats", methods=["GET"])
def get_dashboard_stats():
    """Retrieve aggregations from database to build KPI cards and charts."""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        # Churn stats
        cursor.execute("SELECT COUNT(*) FROM churn_logs")
        total_churn_evals = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM churn_logs WHERE prediction = 'Churn'")
        churn_risk_count = cursor.fetchone()[0]
        
        # Sales stats
        cursor.execute("SELECT COUNT(*), AVG(forecast_sales) FROM sales_logs")
        sales_row = cursor.fetchone()
        total_sales_evals = sales_row[0] or 0
        avg_forecast_revenue = float(sales_row[1]) if sales_row[1] is not None else 1250000.00 # fallback KPI from step 8
        
        # Recommendation stats
        cursor.execute("SELECT COUNT(*) FROM recommendations")
        total_recommendations = cursor.fetchone()[0]
        
        # Property stats
        cursor.execute("SELECT COUNT(*), AVG(price) FROM property_logs")
        prop_row = cursor.fetchone()
        total_properties = prop_row[0] or 0
        avg_property_price = float(prop_row[1]) if prop_row[1] is not None else 8500000.00
        
        # Churn list for chart
        cursor.execute("SELECT prediction, COUNT(*) FROM churn_logs GROUP BY prediction")
        churn_chart_data = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Property locations average price chart data
        cursor.execute("SELECT location, AVG(price), COUNT(*) FROM property_logs GROUP BY location LIMIT 10")
        property_chart_data = [{"location": row[0], "avg_price": float(row[1]), "count": row[2]} for row in cursor.fetchall()]
        
        # Recent logs for activity table
        cursor.execute("SELECT 'Churn Prediction' as type, created_at, 'Result: ' || prediction as details FROM churn_logs UNION ALL "
                       "SELECT 'Sales Forecast' as type, created_at, 'Growth: ' || round(growth_rate, 1) || '%' as details FROM sales_logs UNION ALL "
                       "SELECT 'Product Recommendation' as type, created_at, 'Products: ' || products as details FROM recommendations UNION ALL "
                       "SELECT 'Property Insight' as type, created_at, 'Value: ₹' || round(price, 0) as details FROM property_logs "
                       "ORDER BY created_at DESC LIMIT 8")
        recent_activity = [{"type": row[0], "timestamp": row[1], "details": row[2]} for row in cursor.fetchall()]
        
        conn.close()
        
        # Construct summary response
        return jsonify({
            "kpis": {
                "forecast_revenue": avg_forecast_revenue,
                "customers_at_risk": churn_risk_count,
                "total_churn_evals": total_churn_evals,
                "recommendations_generated": total_recommendations,
                "properties_evaluated": total_properties,
                "avg_property_value": avg_property_price
            },
            "charts": {
                "churn": churn_chart_data,
                "properties": property_chart_data
            },
            "recent_activity": recent_activity
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    # Serve Flask app on port 5050
    app.run(host="0.0.0.0", port=5050, debug=True)
