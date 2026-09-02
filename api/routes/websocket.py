from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal(self, websocket: WebSocket, message: dict):
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        msg_str = json.dumps(message)
        dead_connections = []
        # Iterate over a snapshot to avoid mutation during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_text(msg_str)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

# Dependency injection functions — resolved in main.py
def get_device_list():
    return []

def get_recent_alerts_sync():
    return []

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Load recent alerts from the database for initial state
        recent_alerts = []
        try:
            recent_alerts = await _load_recent_alerts()
        except Exception as e:
            print(f"[WS] Failed to load recent alerts for initial state: {e}")

        initial_state = {
            "type": "initial_state",
            "devices": get_device_list(),
            "recent_alerts": recent_alerts
        }
        await manager.send_personal(websocket, initial_state)
        
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS ERROR] Connection error: {e}")
    finally:
        manager.disconnect(websocket)

# This will be set by main.py to provide actual DB loading
async def _load_recent_alerts():
    return []
