import time
import random
import math

DEVICE_CONFIGS = [
    {"id": "EDGE-001", "name": "Alpha Motor",       "temp_base": 72, "vib_base": 0.14, "curr_base": 4.8, "pres_base": 2.1},
    {"id": "EDGE-002", "name": "Beta Compressor",   "temp_base": 68, "vib_base": 0.18, "curr_base": 5.2, "pres_base": 2.5},
    {"id": "EDGE-003", "name": "Gamma Turbine",     "temp_base": 78, "vib_base": 0.12, "curr_base": 4.2, "pres_base": 1.9},
    {"id": "EDGE-004", "name": "Delta Pump",        "temp_base": 65, "vib_base": 0.22, "curr_base": 5.8, "pres_base": 2.8},
    {"id": "EDGE-005", "name": "Epsilon Generator", "temp_base": 75, "vib_base": 0.10, "curr_base": 4.5, "pres_base": 2.2},
]

class SensorSimulator:
    def __init__(self, config: dict):
        self.device_id = config["id"]
        self.device_name = config["name"]
        self.base_values = {
            "temperature": config["temp_base"],
            "vibration": config["vib_base"],
            "current": config["curr_base"],
            "pressure": config["pres_base"]
        }
        self.anomaly_rate = 0.08  # 8% injection → ~10-15% detected rate
        self.step_count = 0
        self.status = "online"
        self._anomaly_state = None

    def trigger_anomaly(self):
        anomaly_types = ["spike", "drift", "oscillation", "flatline"]
        a_type = random.choice(anomaly_types)
        sensors = list(self.base_values.keys())
        affected = random.sample(sensors, k=random.randint(1, 2))
        
        if a_type == "spike":
            duration = random.randint(1, 3)
            intensity = random.uniform(1.5, 3.0) * random.choice([1, -1])
        elif a_type == "drift":
            duration = random.randint(10, 25)
            intensity = random.uniform(0.1, 0.3)
        elif a_type == "oscillation":
            duration = random.randint(5, 15)
            intensity = random.uniform(0.5, 1.5)
        else: # flatline
            duration = random.randint(3, 8)
            intensity = 0
            
        self._anomaly_state = {
            "type": a_type,
            "duration": duration,
            "intensity": intensity,
            "affected_sensors": affected,
            "steps_remaining": duration,
            "drift_acc": 0
        }

    def trigger_manual_anomaly(self, anomaly_type: str, affected_sensors: list):
        if anomaly_type not in ["spike", "drift", "oscillation", "flatline"]:
            return
        
        if not affected_sensors:
            affected_sensors = list(self.base_values.keys())
            
        if anomaly_type == "spike":
            duration = random.randint(3, 5)
            intensity = random.uniform(1.8, 3.0) * random.choice([1, -1])
        elif anomaly_type == "drift":
            duration = random.randint(15, 30)
            intensity = random.uniform(0.15, 0.35)
        elif anomaly_type == "oscillation":
            duration = random.randint(10, 20)
            intensity = random.uniform(0.8, 1.8)
        else: # flatline
            duration = random.randint(8, 15)
            intensity = 0
            
        self._anomaly_state = {
            "type": anomaly_type,
            "duration": duration,
            "intensity": intensity,
            "affected_sensors": affected_sensors,
            "steps_remaining": duration,
            "drift_acc": 0
        }

    def resolve_anomaly(self):
        self._anomaly_state = None

    def generate_reading(self) -> dict:
        self.step_count += 1
        t = self.step_count
        
        if self._anomaly_state is None and random.random() < self.anomaly_rate:
            self.trigger_anomaly()
            
        # Normal base variations
        reading = {
            "temperature": self.base_values["temperature"] + 8 * math.sin(0.05 * t) + random.gauss(0, 2),
            "vibration": self.base_values["vibration"] + 0.05 * math.sin(0.1 * t) + abs(random.gauss(0, 0.02)),
            "current": self.base_values["current"] + 0.5 * math.sin(0.03 * t) + random.gauss(0, 0.15),
            "pressure": self.base_values["pressure"] + 0.3 * math.sin(0.07 * t) + random.gauss(0, 0.05)
        }
        
        # Apply anomalies
        if self._anomaly_state is not None:
            state = self._anomaly_state
            a_type = state["type"]
            for sensor in state["affected_sensors"]:
                if a_type == "spike":
                    if state["intensity"] > 0:
                        reading[sensor] *= state["intensity"]
                    else:
                        reading[sensor] /= abs(state["intensity"])
                elif a_type == "drift":
                    state["drift_acc"] += state["intensity"]
                    reading[sensor] += state["drift_acc"]
                elif a_type == "oscillation":
                    reading[sensor] += state["intensity"] * math.sin(t * 3.14)
                elif a_type == "flatline":
                    reading[sensor] = self.base_values[sensor] # fixed
            
            state["steps_remaining"] -= 1
            if state["steps_remaining"] <= 0:
                self._anomaly_state = None
                
        # Ensure values don't go negative where physically impossible
        reading["vibration"] = max(0, reading["vibration"])
        reading["current"] = max(0, reading["current"])
        reading["pressure"] = max(0, reading["pressure"])
        
        return reading
