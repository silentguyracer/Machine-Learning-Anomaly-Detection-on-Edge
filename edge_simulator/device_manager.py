import asyncio
from typing import Callable, List
from edge_simulator.sensor_simulator import SensorSimulator, DEVICE_CONFIGS

class DeviceManager:
    def __init__(self):
        self.devices = [SensorSimulator(cfg) for cfg in DEVICE_CONFIGS]
        self._running = False
        self._tasks = []

    def get_devices(self) -> List[dict]:
        return [{"id": d.device_id, "name": d.device_name, "status": d.status} for d in self.devices]

    def get_device_count(self) -> int:
        return len(self.devices)

    async def _device_loop(self, device: SensorSimulator, callback: Callable):
        # Stagger start times slightly
        await asyncio.sleep(0.1 * self.devices.index(device))
        
        while self._running:
            if device.status == "online":
                reading = device.generate_reading()
                data = {
                    "device_id": device.device_id,
                    "device_name": device.device_name,
                    "sensors": reading
                }
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            await asyncio.sleep(0.5)

    def toggle_device(self, device_id: str) -> str:
        for device in self.devices:
            if device.device_id == device_id:
                device.status = "offline" if device.status == "online" else "online"
                return device.status
        return ""

    async def start(self, callback: Callable):
        self._running = True
        self._tasks = [asyncio.create_task(self._device_loop(d, callback)) for d in self.devices]
        
    def trigger_device_anomaly(self, device_id: str, anomaly_type: str, affected_sensors: list) -> bool:
        for device in self.devices:
            if device.device_id == device_id:
                device.trigger_manual_anomaly(anomaly_type, affected_sensors)
                return True
        return False

    def resolve_device_anomaly(self, device_id: str) -> bool:
        for device in self.devices:
            if device.device_id == device_id:
                device.resolve_anomaly()
                return True
        return False

    def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
