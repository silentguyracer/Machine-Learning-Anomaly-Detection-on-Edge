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
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_str)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

# This is a dependency inject function to get devices, will be resolved in main.py
def get_device_list():
    return []

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state
        initial_state = {
            "type": "initial_state",
            "devices": get_device_list(),
            "recent_alerts": []
        }
        await manager.send_personal(websocket, initial_state)
        
        while True:
            # Just keep alive loop
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
