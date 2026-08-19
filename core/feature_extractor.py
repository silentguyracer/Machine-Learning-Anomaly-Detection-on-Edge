import numpy as np
from collections import deque
from typing import Dict, Any

class SensorWindow:
    def __init__(self, window_size=30):
        self.window_size = window_size
        self._windows = {}
        
    def _get_key(self, device_id: str, sensor_name: str) -> str:
        return f"{device_id}_{sensor_name}"

    def add_reading(self, device_id: str, sensor_name: str, value: float):
        key = self._get_key(device_id, sensor_name)
        if key not in self._windows:
            self._windows[key] = deque(maxlen=self.window_size)
        self._windows[key].append(value)

    def get_window(self, device_id: str, sensor_name: str) -> np.ndarray:
        key = self._get_key(device_id, sensor_name)
        if key not in self._windows:
            return np.array([])
        return np.array(self._windows[key])

def compute_zscore(value: float, window: np.ndarray) -> float:
    if len(window) < 5:
        return 0.0
    mean = np.mean(window)
    std = np.std(window)
    if std == 0:
        return 0.0
    return abs(value - mean) / std
