import os
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
import joblib

def generate_synthetic_data(num_samples=5000):
    t = np.arange(num_samples)
    
    temperature = 70 + 8 * np.sin(0.05 * t) + np.random.normal(0, 2, num_samples)
    temperature = np.clip(temperature, 50, 90)
    
    vibration = 0.15 + 0.05 * np.sin(0.1 * t) + np.abs(np.random.normal(0, 0.02, num_samples))
    vibration = np.clip(vibration, 0, 0.5)
    
    current = 4.5 + 0.5 * np.sin(0.03 * t) + np.random.normal(0, 0.15, num_samples)
    current = np.clip(current, 3, 7)
    
    pressure = 2.2 + 0.3 * np.sin(0.07 * t) + np.random.normal(0, 0.05, num_samples)
    pressure = np.clip(pressure, 1, 3.5)
    
    return np.column_stack((temperature, vibration, current, pressure))

def main():
    print("Generating synthetic normal data...")
    X = generate_synthetic_data()
    
    print("Training StandardScaler...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    print("Training Isolation Forest...")
    iso_forest = IsolationForest(n_estimators=100, contamination=0.08, random_state=42)
    iso_forest.fit(X_scaled)
    
    print("Training Local Outlier Factor...")
    lof = LocalOutlierFactor(n_neighbors=20, contamination=0.08, novelty=True)
    lof.fit(X_scaled)
    
    # Save models
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    save_dir = os.path.join(project_root, "models", "saved")
    os.makedirs(save_dir, exist_ok=True)
    
    joblib.dump(scaler, os.path.join(save_dir, "scaler.joblib"))
    joblib.dump(iso_forest, os.path.join(save_dir, "isolation_forest.joblib"))
    joblib.dump(lof, os.path.join(save_dir, "lof.joblib"))
    
    print(f"Models saved successfully to {save_dir}")
    print("Validation results: Models trained on normal baseline data.")

import sqlite3

def retrain_from_db(db_path: str, save_dir: str) -> dict:
    print(f"Retraining models from data source: {db_path}")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}. Run simulation first to collect baseline logs.")
        
    db_uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True, timeout=30.0)
    cursor = conn.cursor()
    
    # Query normal operational readings
    cursor.execute('''
        SELECT temperature, vibration, current, pressure 
        FROM sensor_readings 
        WHERE is_anomaly = 0 
        ORDER BY timestamp DESC 
        LIMIT 5000
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    sample_count = len(rows)
    print(f"Retrieved {sample_count} normal baseline records from SQLite.")
    
    # Require a minimum statistical sample size for scikit-learn models
    if sample_count < 100:
        raise ValueError(f"Fewer than 100 normal operational records available ({sample_count} total). "
                         "Collect more baseline readings before retraining.")
                         
    X = np.array(rows, dtype=np.float64)
    
    # Fit StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Fit Isolation Forest
    iso_forest = IsolationForest(n_estimators=100, contamination=0.06, random_state=42)
    iso_forest.fit(X_scaled)
    
    # Fit Local Outlier Factor
    lof = LocalOutlierFactor(n_neighbors=20, contamination=0.06, novelty=True)
    lof.fit(X_scaled)
    
    # Save the updated models
    os.makedirs(save_dir, exist_ok=True)
    joblib.dump(scaler, os.path.join(save_dir, "scaler.joblib"))
    joblib.dump(iso_forest, os.path.join(save_dir, "isolation_forest.joblib"))
    joblib.dump(lof, os.path.join(save_dir, "lof.joblib"))
    
    print(f"Successfully retrained and saved models to {save_dir}")
    return {
        "status": "success",
        "sample_count": sample_count,
        "contamination": 0.06,
        "n_estimators": 100
    }

if __name__ == "__main__":
    main()
