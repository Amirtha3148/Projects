"""
WebSocket Server for Unity Communication

Streams head pose data to Unity in real-time.
"""

import asyncio
import json
import websockets
from websockets.server import serve
from typing import Optional, Dict, Any, Set, Callable
import threading
import queue
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings


class WebSocketServer:
    """Async WebSocket server for streaming pose data to Unity."""
    
    def __init__(self, host: str = None, port: int = None,
                 on_client_connect: Optional[Callable] = None,
                 on_client_disconnect: Optional[Callable] = None):
        self.host = host or settings.WEBSOCKET_HOST
        self.port = port or settings.WEBSOCKET_PORT
        self._on_connect = on_client_connect
        self._on_disconnect = on_client_disconnect
        self._clients: Set = set()
        self._pose_queue: queue.Queue = queue.Queue(maxsize=10)
        self._server_thread: Optional[threading.Thread] = None
        self._running = False
        self._loop = None
        self._messages_sent = 0
        self._last_send_time = 0
        self._avg_latency = 0
        
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()
        time.sleep(0.5)
        print(f"[WEBSOCKET] Server started on ws://{self.host}:{self.port}")
    
    def _run_server(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            print(f"[WEBSOCKET] Server error: {e}")
        finally:
            self._loop.close()
    
    async def _serve(self) -> None:
        async with serve(self._handle_client, self.host, self.port,
                        ping_interval=20, ping_timeout=10) as server:
            broadcast_task = asyncio.create_task(self._broadcast_loop())
            while self._running:
                await asyncio.sleep(0.1)
            broadcast_task.cancel()
    
    async def _handle_client(self, websocket) -> None:
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"[WEBSOCKET] Client connected: {client_id}")
        self._clients.add(websocket)
        
        if self._on_connect:
            self._on_connect(client_id)
        
        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            print(f"[WEBSOCKET] Client disconnected: {client_id}")
            if self._on_disconnect:
                self._on_disconnect(client_id)
    
    async def _handle_message(self, websocket, message: str) -> None:
        try:
            data = json.loads(message)
            if data.get("command") == "ping":
                await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))
        except json.JSONDecodeError:
            pass
    
    async def _broadcast_loop(self) -> None:
        while self._running:
            try:
                try:
                    pose_data = self._pose_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.001)
                    continue
                
                if not self._clients:
                    continue
                
                message = json.dumps(pose_data)
                disconnected = set()
                
                for client in self._clients:
                    try:
                        await client.send(message)
                    except:
                        disconnected.add(client)
                
                self._clients -= disconnected
                self._messages_sent += 1
            except Exception as e:
                await asyncio.sleep(0.01)
    
    def send_pose(self, pose_data: Dict[str, Any]) -> None:
        try:
            if self._pose_queue.full():
                try:
                    self._pose_queue.get_nowait()
                except queue.Empty:
                    pass
            self._pose_queue.put_nowait(pose_data)
        except queue.Full:
            pass
    
    def stop(self) -> None:
        self._running = False
        if self._server_thread:
            self._server_thread.join(timeout=2.0)
        print("[WEBSOCKET] Server stopped")
    
    @property
    def client_count(self) -> int:
        return len(self._clients)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "clients": self.client_count,
            "messages_sent": self._messages_sent,
            "running": self._running
        }
