import os
import joblib
import numpy as np
from core.feature_extractor import SensorWindow, compute_zscore
from core.autoencoder import NeuralAutoencoder

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
        self.autoencoder = None
        
        # Adjustable parameters for tuning (5-model ensemble)
        self.w_iso = 0.28
        self.w_ae = 0.24
        self.w_lof = 0.16
        self.w_stat = 0.18
        self.w_range = 0.14
        self.anomaly_threshold = 0.55
        self.z_threshold = 3.0
        
        self.load_models()

    def load_models(self):
        try:
            save_dir = os.path.join(self.project_root, "models", "saved")
            self.scaler = joblib.load(os.path.join(save_dir, "scaler.joblib"))
            self.iso_forest = joblib.load(os.path.join(save_dir, "isolation_forest.joblib"))
            self.lof = joblib.load(os.path.join(save_dir, "lof.joblib"))
            
            ae_path = os.path.join(save_dir, "autoencoder.joblib")
            if os.path.exists(ae_path):
                self.autoencoder = NeuralAutoencoder.load(ae_path)
            else:
                self.autoencoder = None
                
            self.models_loaded = True
            print("AnomalyDetector: Full ML Ensemble (IF, LOF, Autoencoder, Stat, Range) loaded.")
        except Exception as e:
            print(f"AnomalyDetector: Failed to load models ({e}). Using fallback methods only.")
            self.models_loaded = False

    def reload_models(self) -> bool:
        self.load_models()
        return self.models_loaded

    def get_config(self) -> dict:
        return {
            "w_iso": self.w_iso,
            "w_ae": self.w_ae,
            "w_lof": self.w_lof,
            "w_stat": self.w_stat,
            "w_range": self.w_range,
            "anomaly_threshold": self.anomaly_threshold,
            "z_threshold": self.z_threshold
        }

    def update_config(self, config: dict):
        self.w_iso = float(config.get("w_iso", self.w_iso))
        self.w_ae = float(config.get("w_ae", self.w_ae))
        self.w_lof = float(config.get("w_lof", self.w_lof))
        self.w_stat = float(config.get("w_stat", self.w_stat))
        self.w_range = float(config.get("w_range", self.w_range))
        self.anomaly_threshold = float(config.get("anomaly_threshold", self.anomaly_threshold))
        self.z_threshold = float(config.get("z_threshold", self.z_threshold))
        
        # Normalize weights so they sum to 1.0
        total = self.w_iso + self.w_ae + self.w_lof + self.w_stat + self.w_range
        if total > 0:
            self.w_iso = round(self.w_iso / total, 3)
            self.w_ae = round(self.w_ae / total, 3)
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
            "autoencoder": False,
            "lof": False,
            "statistical": False,
            "range": False
        }

        score_iso = 0.0
        score_lof = 0.0
        score_ae = 0.0
        attributions = {"temperature": 25.0, "vibration": 25.0, "current": 25.0, "pressure": 25.0}
        latent_coords = [0.0, 0.0]

        if self.models_loaded and self.scaler is not None:
            scaled_features = self.scaler.transform(feature_array)

            # 1. Isolation Forest
            if self.iso_forest:
                iso_pred = self.iso_forest.predict(scaled_features)[0]
                model_verdicts["isolation_forest"] = bool(iso_pred == -1)
                score_iso = float(max(0.0, -self.iso_forest.decision_function(scaled_features)[0]))

            # 2. Local Outlier Factor
            if self.lof:
                lof_pred = self.lof.predict(scaled_features)[0]
                model_verdicts["lof"] = bool(lof_pred == -1)
                score_lof = float(max(0.0, -self.lof.score_samples(scaled_features)[0] - 1.5))

            # 3. Neural Autoencoder
            if self.autoencoder:
                ae_mse, ae_anomaly, attr_list, z_coords = self.autoencoder.predict_sample(scaled_features[0])
                model_verdicts["autoencoder"] = bool(ae_anomaly)
                score_ae = float(min(1.0, ae_mse * 1.8))
                latent_coords = z_coords
                attributions = {
                    "temperature": attr_list[0],
                    "vibration": attr_list[1],
                    "current": attr_list[2],
                    "pressure": attr_list[3]
                }

        # 4. Statistical & Range Checks
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

        # 5. Ensemble Score Calculation
        z_score_norm = float(min(1.0, max_zscore / 5.0))

        if self.models_loaded:
            iso_norm = float(min(1.0, score_iso * 2.5))
            lof_norm = float(min(1.0, score_lof * 0.5))
            ae_norm = float(min(1.0, score_ae))
            
            ensemble_score = (
                (iso_norm * self.w_iso) +
                (ae_norm * self.w_ae) +
                (lof_norm * self.w_lof) +
                (z_score_norm * self.w_stat) +
                ((1.0 if model_verdicts["range"] else 0.0) * self.w_range)
            )
        else:
            w_sum = self.w_stat + self.w_range
            w_stat_norm = self.w_stat / w_sum if w_sum > 0 else 0.6
            w_range_norm = self.w_range / w_sum if w_sum > 0 else 0.4
            ensemble_score = (z_score_norm * w_stat_norm) + ((1.0 if model_verdicts["range"] else 0.0) * w_range_norm)

        ensemble_score = float(min(1.0, ensemble_score))
        is_anomaly = bool(
            ensemble_score > self.anomaly_threshold or 
            model_verdicts["range"] or 
            model_verdicts["statistical"] or 
            (model_verdicts["autoencoder"] and model_verdicts["isolation_forest"])
        )

        # Prioritize top attributing sensor if anomalous_sensors is empty
        if is_anomaly and not anomalous_sensors:
            top_sensor = max(attributions, key=attributions.get)
            anomalous_sensors.append(top_sensor)

        return ensemble_score, is_anomaly, model_verdicts, anomalous_sensors, attributions, latent_coords
