from enum import Enum
from dataclasses import dataclass
from typing import List
import json
import uuid

class Severity(str, Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

SEVERITY_COLORS = {
    Severity.NORMAL: "#22c55e",
    Severity.LOW: "#eab308",
    Severity.MEDIUM: "#f97316",
    Severity.HIGH: "#ef4444",
    Severity.CRITICAL: "#dc2626"
}

@dataclass
class Alert:
    id: str
    device_id: str
    device_name: str
    severity: Severity
    message: str
    timestamp: str
    anomaly_score: float
    anomalous_sensors: List[str]
    
    def to_dict(self) -> dict:
        return {
            "type": "alert",
            "id": self.id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "anomaly_score": self.anomaly_score,
            "anomalous_sensors": self.anomalous_sensors,
            "color": SEVERITY_COLORS[self.severity]
        }

def determine_severity(anomaly_score: float) -> Severity:
    if anomaly_score < 0.3:
        return Severity.NORMAL
    elif anomaly_score < 0.5:
        return Severity.LOW
    elif anomaly_score < 0.7:
        return Severity.MEDIUM
    elif anomaly_score < 0.85:
        return Severity.HIGH
    else:
        return Severity.CRITICAL

def generate_alert_message(device_name: str, severity: Severity, anomalous_sensors: List[str]) -> str:
    sensors = ", ".join(anomalous_sensors)
    if severity == Severity.CRITICAL:
        return f"CRITICAL FAILURE IMMINENT on {device_name}. Sensors out of bound: {sensors}"
    elif severity == Severity.HIGH:
        return f"Abnormal pattern detected on {device_name}. Check {sensors} immediately."
    elif severity == Severity.MEDIUM:
        return f"Moderate deviations observed on {device_name} ({sensors})."
    elif severity == Severity.LOW:
        return f"Minor fluctuations on {device_name} ({sensors}). Monitor closely."
    return f"Normal operation for {device_name}."
