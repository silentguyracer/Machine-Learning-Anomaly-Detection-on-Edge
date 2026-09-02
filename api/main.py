import os
import sys
import asyncio
import traceback
from datetime import datetime, timezone
import uuid
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

# Ensure we can import from core and edge_simulator
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.feature_extractor import SensorWindow
from core.anomaly_detector import AnomalyDetector
from core.alert_manager import determine_severity, generate_alert_message, Alert
from edge_simulator.device_manager import DeviceManager
from api.database import init_db, DatabaseManager, DB_PATH
from api.routes.websocket import router as ws_router, manager as ws_manager
from api.routes.data import router as data_router
import api.routes.websocket as ws_module
import api.routes.data as data_module

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Initializing Database...")
    await init_db(actual_db_path)
    
    print("Starting Database Worker...")
    await db_manager.start()
    
    print("Starting Device Manager...")
    await device_manager.start(process_reading)
    
    asyncio.create_task(stats_loop())
    print("System ready!")
    
    yield
    
    # Shutdown
    print("Shutting down...")
    device_manager.stop()
    await db_manager.stop()

app = FastAPI(title="Edge Anomaly Detection", lifespan=lifespan)

# Setup Paths
static_dir = os.path.join(project_root, "dashboard", "static")
templates_dir = os.path.join(project_root, "dashboard", "templates")
actual_db_path = os.path.join(project_root, DB_PATH)

# Create dirs if missing
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)
os.makedirs(os.path.dirname(actual_db_path), exist_ok=True)

# Mount static and templates
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Global State
device_manager = DeviceManager()
detector = AnomalyDetector(project_root)
sensor_window = SensorWindow(window_size=30)
start_time = datetime.now(timezone.utc)
db_manager = DatabaseManager(actual_db_path)

# Update route dependencies
ws_module.get_device_list = device_manager.get_devices
data_module.get_device_list = device_manager.get_devices
data_module.get_uptime = lambda: int((datetime.now(timezone.utc) - start_time).total_seconds())
data_module._get_total_readings = lambda: total_readings
data_module._get_total_anomalies = lambda: total_anomalies
data_module.device_manager = device_manager
data_module.detector = detector
data_module.db_manager = db_manager

# Wire up recent alerts loader for WebSocket initial state
from api.database import get_recent_alerts
async def _load_recent_alerts_from_db():
    try:
        return await get_recent_alerts(actual_db_path, limit=20)
    except Exception:
        return []
ws_module._load_recent_alerts = _load_recent_alerts_from_db

app.include_router(ws_router)
app.include_router(data_router)

total_readings = 0
total_anomalies = 0

async def process_reading(reading: dict):
    global total_readings, total_anomalies
    try:
        device_id = reading["device_id"]
        device_name = reading["device_name"]
        timestamp = datetime.now(timezone.utc).isoformat()
        reading["timestamp"] = timestamp

        # 1. Update sensor window
        for sensor, val in reading["sensors"].items():
            sensor_window.add_reading(device_id, sensor, val)

        # 2. Run detector
        anomaly_score, is_anomaly, model_verdicts, anomalous_sensors = detector.detect(reading, sensor_window)
        severity = determine_severity(anomaly_score)
        
        # Fix: if detector flagged anomaly but score yields NORMAL severity, bump to LOW minimum
        from core.alert_manager import Severity
        if is_anomaly and severity == Severity.NORMAL:
            severity = Severity.LOW

        # Only expose the 3 model keys the dashboard expects
        frontend_verdicts = {
            "isolation_forest": model_verdicts.get("isolation_forest", False),
            "lof": model_verdicts.get("lof", False),
            "statistical": model_verdicts.get("statistical", False),
        }

        # 3. Build update message
        msg = {
            "type": "sensor_update",
            "device_id": device_id,
            "device_name": device_name,
            "timestamp": timestamp,
            "sensors": reading["sensors"],
            "anomaly_score": round(float(anomaly_score), 4),
            "is_anomaly": bool(is_anomaly),
            "severity": severity.value,
            "model_verdicts": frontend_verdicts,
            "anomalous_sensors": anomalous_sensors,
            "alert_message": ""
        }

        # 4. Broadcast sensor update
        await ws_manager.broadcast(msg)

        # 5. Handle anomaly / Alert
        if is_anomaly:
            total_anomalies += 1
            msg["alert_message"] = generate_alert_message(device_name, severity, anomalous_sensors)

            alert = Alert(
                id=str(uuid.uuid4()),
                device_id=device_id,
                device_name=device_name,
                severity=severity,
                message=msg["alert_message"],
                timestamp=timestamp,
                anomaly_score=float(anomaly_score),
                anomalous_sensors=anomalous_sensors
            )
            alert_dict = alert.to_dict()
            await ws_manager.broadcast(alert_dict)
            db_manager.queue_alert(alert_dict)

        # 6. Store reading
        db_reading = msg.copy()
        db_manager.queue_reading(db_reading)

        # 7. Increment counters
        total_readings += 1

    except Exception as e:
        print(f"[ERROR] process_reading failed for {reading.get('device_id', '?')}: {e}")
        traceback.print_exc()

async def stats_loop():
    while True:
        await asyncio.sleep(5)
        rate = (total_anomalies / total_readings * 100) if total_readings > 0 else 0.0
        stats_msg = {
            "type": "system_stats",
            "total_readings": total_readings,
            "total_anomalies": total_anomalies,
            "anomaly_rate": round(rate, 2),
            "active_devices": len([d for d in device_manager.get_devices() if d.get("status") == "online"]),
            "uptime_seconds": int((datetime.now(timezone.utc) - start_time).total_seconds())
        }
        await ws_manager.broadcast(stats_msg)
        print(f"[STATS] readings={total_readings} anomalies={total_anomalies} rate={rate:.1f}%")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
