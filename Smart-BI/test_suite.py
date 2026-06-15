import urllib.request
import json
import sqlite3
import os
import time
import subprocess
import sys

# Test settings
BACKEND_URL = "http://127.0.0.1:5050"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_bi.db")

def send_post(endpoint, data):
    url = f"{BACKEND_URL}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error calling {url}: {e}")
        return 500, None

def verify_database_logs():
    print("\n--- Database Integrity & Verification ---")
    if not os.path.exists(DB_PATH):
        print(f"FAIL: SQLite database not found at {DB_PATH}")
        return False
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check Churn logs
        cursor.execute("SELECT COUNT(*) FROM churn_logs")
        churn_count = cursor.fetchone()[0]
        print(f"Churn Predictions Logged: {churn_count} (Expected: >= 1)")
        
        # Check Property logs
        cursor.execute("SELECT COUNT(*) FROM property_logs")
        prop_count = cursor.fetchone()[0]
        print(f"Property Predictions Logged: {prop_count} (Expected: >= 1)")
        
        # Check Recommendations logs
        cursor.execute("SELECT COUNT(*) FROM recommendations")
        rec_count = cursor.fetchone()[0]
        print(f"Recommendations Logged: {rec_count} (Expected: >= 1)")
        
        # Check Sales logs
        cursor.execute("SELECT COUNT(*) FROM sales_logs")
        sales_count = cursor.fetchone()[0]
        print(f"Sales Forecasts Logged: {sales_count} (Expected: >= 1)")
        
        conn.close()
        if churn_count >= 1 and prop_count >= 1 and rec_count >= 1 and sales_count >= 1:
            print("Database logging integrity checks PASSED successfully!")
            return True
        else:
            print("FAIL: One or more log tables did not record transactions.")
            return False
    except Exception as e:
        print(f"FAIL: Database integrity check failed. Error: {e}")
        return False

def main():
    print("==================================================")
    # 1. Start Flask in background if it's not running
    print("Starting Flask server for API integration verification...")
    # Clean old db if exists to test clean assertions
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass
            
    app_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    proc = subprocess.Popen([sys.executable, app_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(4) # Give Flask time to spin up and load the Prophet and Movie models
    
    success = True
    try:
        # Test Churn API
        print("\nTesting Customer Churn API...")
        churn_data = {
            "gender": "Male",
            "tenure": 12,
            "MonthlyCharges": 80.0,
            "Contract": "Month-to-month",
            "InternetService": "Fiber optic"
        }
        status, response = send_post("/predict", churn_data)
        if status == 200 and response and "prediction" in response:
            print(f"PASS: Churn API returned prediction={response['prediction']}, probability={response['probability']}")
        else:
            print(f"FAIL: Churn API returned status={status}, response={response}")
            success = False
            
        # Test Property Insights API
        print("\nTesting Property Insights Valuation API...")
        property_data = {
            "area": 1500,
            "bedrooms": 3,
            "bathrooms": 2,
            "location": "medium"
        }
        status, response = send_post("/api/predict-price", property_data)
        if status == 200 and response and "price" in response:
            print(f"PASS: Property API returned price={response['price']}")
        else:
            print(f"FAIL: Property API returned status={status}, response={response}")
            success = False
            
        # Test Product Recommendations API
        print("\nTesting Product Recommendations API...")
        rec_data = {
            "customer_id": 15
        }
        status, response = send_post("/api/recommend", rec_data)
        if status == 200 and response and "recommendations" in response:
            print(f"PASS: Recommender API returned: {response['recommendations']}")
        else:
            print(f"FAIL: Recommender API returned status={status}, response={response}")
            success = False
            
        # Test Sales Forecast API
        print("\nTesting Sales Forecast API...")
        sales_data = {
            "periods": 30
        }
        status, response = send_post("/api/forecast", sales_data)
        if status == 200 and response and "forecast" in response:
            print(f"PASS: Forecast API returned {len(response['forecast'])} daily forecasts. Horizon sum={response['summary']['total_sales']}")
        else:
            print(f"FAIL: Forecast API returned status={status}, response={response}")
            success = False
            
        # 2. Verify database records
        db_passed = verify_database_logs()
        if not db_passed:
            success = False
            
    finally:
        # Kill Flask background process
        print("\nStopping local Flask test server...")
        proc.terminate()
        proc.wait()
        
    print("==================================================")
    if success:
        print("ALL AUTOMATED TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("TEST RUN ENCOUNTERED FAILURES.")
        sys.exit(1)

if __name__ == "__main__":
    main()
