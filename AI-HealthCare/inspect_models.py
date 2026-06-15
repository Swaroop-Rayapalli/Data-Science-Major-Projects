import joblib

try:
    scaler = joblib.load('trained-models/heart_disease_scaler.pkl')
    print("Scaler:", type(scaler))
    if hasattr(scaler, 'feature_names_in_'):
        print("Scaler Features:", scaler.feature_names_in_)
    else:
        print("Scaler Features: Not found directly.")
except Exception as e:
    print("Error loading scaler:", e)
