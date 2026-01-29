"""
WebSocket Handler for Live Updates
Sends P&L and Greeks updates every 1 second
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import asyncio
import json
from datetime import datetime
from utils.logger import logger
from services.portfolio_service import PortfolioService
from main import db_manager

router = APIRouter()

class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                dead_connections.append(connection)
        
        # Remove dead connections
        for conn in dead_connections:
            self.disconnect(conn)

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates"""
    await manager.connect(websocket)
    try:
        # Keep connection alive and listen for messages
        while True:
            data = await websocket.receive_text()
            # Echo back or handle client messages if needed
            logger.debug(f"Received WS message: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def broadcast_loop():
    """Continuous broadcast loop - sends updates every 1 second"""
    while True:
        try:
            if manager.active_connections:
                # Calculate live portfolio
                conn = db_manager.get_connection()
                portfolio_service = PortfolioService(conn)
                metrics = portfolio_service.calculate_live_portfolio()
                
                # Add timestamp
                metrics['timestamp'] = datetime.now().isoformat()
                metrics['type'] = 'live_update'
                
                # Broadcast to all clients
                await manager.broadcast(metrics)
            
            await asyncio.sleep(1)  # 1 second interval
        except Exception as e:
            logger.error(f"Broadcast loop error: {e}")
            await asyncio.sleep(1)

async def start_websocket_broadcast():
    """Start the background broadcast task"""
    asyncio.create_task(broadcast_loop())
    logger.info("✅ WebSocket broadcast loop started")
