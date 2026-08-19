import os
import joblib
import numpy as np
from core.feature_extractor import SensorWindow, compute_zscore

SENSOR_RANGES = {
    "temperature": (50.0, 90.0),
    "vibration": (0.0, 0.5),
    "current": (3.0, 7.0),
    "pressure": (1.0, 3.5),
}

class AnomalyDetector:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.models_loaded = False
        self.scaler = None
        self.iso_forest = None
        self.lof = None
        
        # Adjustable parameters for tuning
        self.w_iso = 0.35
        self.w_lof = 0.15
        self.w_stat = 0.30
        self.w_range = 0.20
        self.anomaly_threshold = 0.58
        self.z_threshold = 3.0
        
        self.load_models()

    def load_models(self):
        try:
            save_dir = os.path.join(self.project_root, "models", "saved")
            self.scaler = joblib.load(os.path.join(save_dir, "scaler.joblib"))
            self.iso_forest = joblib.load(os.path.join(save_dir, "isolation_forest.joblib"))
            self.lof = joblib.load(os.path.join(save_dir, "lof.joblib"))
            self.models_loaded = True
            print("AnomalyDetector: ML Models loaded successfully.")
        except Exception as e:
            print(f"AnomalyDetector: Failed to load models ({e}). Using fallback methods only.")
            self.models_loaded = False

    def reload_models(self) -> bool:
        self.load_models()
        return self.models_loaded

    def get_config(self) -> dict:
        return {
            "w_iso": self.w_iso,
            "w_lof": self.w_lof,
            "w_stat": self.w_stat,
            "w_range": self.w_range,
            "anomaly_threshold": self.anomaly_threshold,
            "z_threshold": self.z_threshold
        }

    def update_config(self, config: dict):
        self.w_iso = float(config.get("w_iso", self.w_iso))
        self.w_lof = float(config.get("w_lof", self.w_lof))
        self.w_stat = float(config.get("w_stat", self.w_stat))
        self.w_range = float(config.get("w_range", self.w_range))
        self.anomaly_threshold = float(config.get("anomaly_threshold", self.anomaly_threshold))
        self.z_threshold = float(config.get("z_threshold", self.z_threshold))
        
        # Normalize weights so they sum to 1.0
        total = self.w_iso + self.w_lof + self.w_stat + self.w_range
        if total > 0:
            self.w_iso = round(self.w_iso / total, 3)
            self.w_lof = round(self.w_lof / total, 3)
            self.w_stat = round(self.w_stat / total, 3)
            self.w_range = round(self.w_range / total, 3)

    def detect(self, reading: dict, sensor_window: SensorWindow) -> tuple:
        device_id = reading.get("device_id")
        features = [
            float(reading.get("sensors", {}).get("temperature", 70.0)),
            float(reading.get("sensors", {}).get("vibration", 0.15)),
            float(reading.get("sensors", {}).get("current", 4.5)),
            float(reading.get("sensors", {}).get("pressure", 2.2))
        ]

        feature_array = np.array(features, dtype=np.float64).reshape(1, -1)

        model_verdicts = {
            "isolation_forest": False,
            "lof": False,
            "statistical": False,
            "range": False
        }

        score_iso = 0.0
        score_lof = 0.0

        if self.models_loaded:
            scaled_features = self.scaler.transform(feature_array)

            # Isolation Forest — convert numpy bool_ to Python bool
            iso_pred = self.iso_forest.predict(scaled_features)[0]
            model_verdicts["isolation_forest"] = bool(iso_pred == -1)
            score_iso = float(max(0.0, -self.iso_forest.decision_function(scaled_features)[0]))

            # LOF
            lof_pred = self.lof.predict(scaled_features)[0]
            model_verdicts["lof"] = bool(lof_pred == -1)
            score_lof = float(max(0.0, -self.lof.score_samples(scaled_features)[0] - 1.5))

        # Statistical & Range Checks
        max_zscore = 0.0
        anomalous_sensors = []

        sensor_names = ["temperature", "vibration", "current", "pressure"]
        for sensor, val in zip(sensor_names, features):
            # Range check
            min_val, max_val = SENSOR_RANGES[sensor]
            if val < min_val or val > max_val:
                model_verdicts["range"] = True
                if sensor not in anomalous_sensors:
                    anomalous_sensors.append(sensor)

            # Z-score check
            window = sensor_window.get_window(device_id, sensor)
            if len(window) > 0:
                z = float(compute_zscore(val, window))
                if z > self.z_threshold:
                    model_verdicts["statistical"] = True
                    if sensor not in anomalous_sensors:
                        anomalous_sensors.append(sensor)
                max_zscore = max(max_zscore, z)

        # Ensemble Score — all values forced to Python float
        z_score_norm = float(min(1.0, max_zscore / 5.0))

        if self.models_loaded:
            iso_norm = float(min(1.0, score_iso * 2.5))
            lof_norm = float(min(1.0, score_lof * 0.5))
            ensemble_score = (iso_norm * self.w_iso) + (lof_norm * self.w_lof) + (z_score_norm * self.w_stat) + (1.0 if model_verdicts["range"] else 0.0) * self.w_range
        else:
            w_sum = self.w_stat + self.w_range
            w_stat_norm = self.w_stat / w_sum if w_sum > 0 else 0.6
            w_range_norm = self.w_range / w_sum if w_sum > 0 else 0.4
            ensemble_score = (z_score_norm * w_stat_norm) + (1.0 if model_verdicts["range"] else 0.0) * w_range_norm

        ensemble_score = float(min(1.0, ensemble_score))
        is_anomaly = bool(ensemble_score > self.anomaly_threshold or model_verdicts["range"] or model_verdicts["statistical"])

        # If models flagged anomaly but no per-sensor attribution yet, find the
        # highest-deviation sensor from its window to give the dashboard context
        if is_anomaly and not anomalous_sensors:
            best_sensor = None
            best_dev = 0.0
            for sensor, val in zip(sensor_names, features):
                window = sensor_window.get_window(device_id, sensor)
                if len(window) > 1:
                    z = float(compute_zscore(val, window))
                    if z > best_dev:
                        best_dev = z
                        best_sensor = sensor
            if best_sensor:
                anomalous_sensors.append(best_sensor)

        return ensemble_score, is_anomaly, model_verdicts, anomalous_sensors
