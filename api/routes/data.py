from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, Callable, List
from pydantic import BaseModel
from api.database import DB_PATH, get_recent_alerts, get_history
import os
import csv
import io
import asyncio
from models.train_models import retrain_from_db

router = APIRouter()
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
actual_db_path = os.path.join(project_root, DB_PATH)

# These are set by main.py at startup to inject live state
def get_device_list():
    return []

def get_uptime():
    return 0

# In-memory counters injected from main.py
_get_total_readings: Callable = lambda: 0
_get_total_anomalies: Callable = lambda: 0

# Device manager reference injected from main.py
device_manager = None
detector = None

class AnomalyTriggerRequest(BaseModel):
    anomaly_type: str
    affected_sensors: List[str]

class ConfigUpdateRequest(BaseModel):
    w_iso: Optional[float] = None
    w_lof: Optional[float] = None
    w_stat: Optional[float] = None
    w_range: Optional[float] = None
    anomaly_threshold: Optional[float] = None
    z_threshold: Optional[float] = None

@router.get("/api/stats")
async def api_get_stats():
    total_readings = _get_total_readings()
    total_anomalies = _get_total_anomalies()
    rate = (total_anomalies / total_readings * 100) if total_readings > 0 else 0.0
    return {
        "total_readings": total_readings,
        "total_anomalies": total_anomalies,
        "anomaly_rate": round(rate, 2),
        "active_devices": len([d for d in get_device_list() if d.get("status") == "online"]),
        "uptime_seconds": get_uptime(),
    }

@router.get("/api/alerts")
async def api_get_alerts(limit: int = 50):
    return await get_recent_alerts(actual_db_path, limit)

@router.get("/api/history")
async def api_get_history(device_id: Optional[str] = None, limit: int = 100):
    return await get_history(actual_db_path, device_id, limit)

@router.get("/api/devices")
async def api_get_devices():
    return get_device_list()

@router.post("/api/devices/{device_id}/trigger_anomaly")
async def api_trigger_anomaly(device_id: str, payload: AnomalyTriggerRequest):
    if device_manager is None:
        raise HTTPException(status_code=503, detail="Device manager not loaded on edge server")
    success = device_manager.trigger_device_anomaly(
        device_id, payload.anomaly_type, payload.affected_sensors
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    return {"status": "success", "message": f"Anomaly {payload.anomaly_type} triggered on {device_id}"}

@router.get("/api/config")
async def api_get_config():
    if detector is None:
        raise HTTPException(status_code=503, detail="Detector not loaded on edge server")
    return detector.get_config()

@router.post("/api/config")
async def api_update_config(payload: ConfigUpdateRequest):
    if detector is None:
        raise HTTPException(status_code=503, detail="Detector not loaded on edge server")
    
    # Exclude unset fields from the payload dict
    update_data = payload.model_dump(exclude_unset=True)
    detector.update_config(update_data)
    return {"status": "success", "config": detector.get_config()}

@router.post("/api/devices/{device_id}/resolve_anomaly")
async def api_resolve_anomaly(device_id: str):
    if device_manager is None:
        raise HTTPException(status_code=503, detail="Device manager not loaded on edge server")
    success = device_manager.resolve_device_anomaly(device_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    return {"status": "success", "message": f"Remedy initiated. Anomaly resolved on {device_id}"}

@router.get("/api/alerts/export")
async def api_export_alerts():
    # Fetch recent anomaly events (limit to 1000 for size efficiency)
    alerts = await get_recent_alerts(actual_db_path, limit=1000)
    
    # Write to a string stream in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        "Event ID", "Device ID", "Device Name", "Timestamp", 
        "Severity", "Anomaly Score", "Affected Sensors", "Alert Message"
    ])
    
    for alert in alerts:
        writer.writerow([
            alert.get("id"),
            alert.get("device_id"),
            alert.get("device_name"),
            alert.get("timestamp"),
            alert.get("severity"),
            alert.get("anomaly_score"),
            ", ".join(alert.get("anomalous_sensors", [])),
            alert.get("message")
        ])
        
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=anomaly_alerts_export.csv"}
    )

@router.post("/api/models/retrain")
async def api_retrain_models():
    if detector is None:
        raise HTTPException(status_code=503, detail="Detector not loaded on edge server")
        
    save_dir = os.path.join(project_root, "models", "saved")
    try:
        # Run training in background thread executor to prevent blocking
        stats = await asyncio.to_thread(retrain_from_db, actual_db_path, save_dir)
        
        # Hot-swap models in memory
        success = detector.reload_models()
        if not success:
            raise HTTPException(status_code=500, detail="Models retrained, but hot-swap reload failed.")
            
        return {
            "status": "success",
            "message": "Models retrained and adapted to edge database.",
            "stats": stats
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retraining loop error: {str(e)}")

@router.post("/api/devices/{device_id}/toggle")
async def api_toggle_device(device_id: str):
    if device_manager is None:
        raise HTTPException(status_code=503, detail="Device manager not loaded on edge server")
    status = device_manager.toggle_device(device_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
        
    from api.routes.websocket import manager as ws_manager
    await ws_manager.broadcast({
        "type": "device_status_update",
        "device_id": device_id,
        "status": status
    })
    
    return {"status": "success", "device_status": status, "message": f"Device {device_id} is now {status}"}
