from typing import List
from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

    async def send_event(self, topic: str, data: dict):
        await self.broadcast({
            "type": "event",
            "timestamp": data.get("timestamp", 0),
            "topic": topic,
            "data": data,
        })

    async def send_workflow_status(self, wf_id: str, status: str, node: str | None = None):
        await self.broadcast({
            "type": "workflow.status",
            "wid": wf_id,
            "status": status,
            "node": node,
        })


manager = ConnectionManager()