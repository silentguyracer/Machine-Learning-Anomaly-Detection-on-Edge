from collections import deque
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Tuple

class PredictiveMaintenanceEngine:
    """
    Industrial Predictive Maintenance (PdM) & Prognostics Engine for Edge Devices.
    Tracks health degradation, computes Remaining Useful Life (RUL), and issues early warnings.
    """
    def __init__(self, history_len: int = 50):
        self.history_len = history_len
        # Per-device telemetry history: {device_id: deque of (timestamp, score, is_anomaly)}
        self.device_history: Dict[str, deque] = {}
        self.device_health: Dict[str, float] = {}
        self.device_rul: Dict[str, int] = {}
        self.device_degradation_state: Dict[str, str] = {}

    def _get_history(self, device_id: str) -> deque:
        if device_id not in self.device_history:
            self.device_history[device_id] = deque(maxlen=self.history_len)
            self.device_health[device_id] = 100.0
            self.device_rul[device_id] = 720  # 12 hours nominal baseline
            self.device_degradation_state[device_id] = "HEALTHY"
        return self.device_history[device_id]

    def update_telemetry(self, device_id: str, anomaly_score: float, is_anomaly: bool, sensors: dict) -> Tuple[float, int, str]:
        """
        Updates device condition, computes rolling Health Index (0-100%) and estimated RUL in minutes.
        Returns: (health_index, rul_minutes, condition_state)
        """
        history = self._get_history(device_id)
        now = datetime.now(timezone.utc).timestamp()
        history.append((now, anomaly_score, is_anomaly))

        # 1. Base score deduction from recent anomaly severity
        recent_scores = [item[1] for item in history]
        recent_anomalies = [item[2] for item in history]
        
        # Exponential moving penalty
        mean_score = float(np.mean(recent_scores)) if recent_scores else 0.0
        anomaly_density = float(np.mean(recent_anomalies)) if recent_anomalies else 0.0
        
        # Thermal / vibration stress penalty
        vib = float(sensors.get("vibration", 0.15))
        temp = float(sensors.get("temperature", 70.0))
        stress_penalty = 0.0
        if vib > 0.35:
            stress_penalty += (vib - 0.35) * 40.0
        if temp > 82.0:
            stress_penalty += (temp - 82.0) * 1.5
            
        raw_health = 100.0 - (mean_score * 45.0) - (anomaly_density * 35.0) - stress_penalty
        
        # Smooth with previous health score
        prev_health = self.device_health.get(device_id, 100.0)
        smoothed_health = float(0.85 * prev_health + 0.15 * raw_health)
        smoothed_health = max(5.0, min(100.0, smoothed_health))
        self.device_health[device_id] = round(smoothed_health, 1)

        # 2. Remaining Useful Life (RUL) estimation
        if len(history) >= 10:
            # Linear degradation rate per second
            times = np.array([item[0] for item in history])
            scores = np.array([item[1] for item in history])
            dt = max(1.0, times[-1] - times[0])
            score_delta = scores[-1] - scores[0]
            
            if score_delta > 0.02:
                # Degrading trend: estimate seconds until failure threshold (1.0)
                rate_per_min = (score_delta / dt) * 60.0
                remaining_margin = max(0.01, 1.0 - mean_score)
                rul_mins = int(max(5, (remaining_margin / rate_per_min)))
            else:
                # Stable or improving
                rul_mins = int(smoothed_health * 7.2)  # 100% -> 720 mins (12h)
        else:
            rul_mins = int(smoothed_health * 7.2)

        self.device_rul[device_id] = rul_mins

        # 3. Determine Condition State
        if smoothed_health >= 80.0:
            state = "OPTIMAL"
        elif smoothed_health >= 60.0:
            state = "GOOD"
        elif smoothed_health >= 40.0:
            state = "DEGRADING"
        elif smoothed_health >= 20.0:
            state = "WARNING"
        else:
            state = "CRITICAL"

        self.device_degradation_state[device_id] = state
        return self.device_health[device_id], rul_mins, state

    def get_device_summary(self, device_id: str) -> dict:
        return {
            "health_score": self.device_health.get(device_id, 100.0),
            "rul_minutes": self.device_rul.get(device_id, 720),
            "state": self.device_degradation_state.get(device_id, "OPTIMAL")
        }
