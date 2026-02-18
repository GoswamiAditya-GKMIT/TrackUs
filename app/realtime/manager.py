import logging
from typing import Dict, List, Optional
from fastapi import WebSocket, status

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections grouped by group_id and user_id.
    Supports optional Redis Pub/Sub for cross-server broadcasting.
    """

    def __init__(self, pubsub_manager=None):
        # Maps room_id -> {user_id: [WebSocket]}
        self.active_connections: Dict[str, Dict[str, List[WebSocket]]] = {}
        self.pubsub = pubsub_manager  # Optional Redis Pub/Sub manager

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        """
        Register a new connection for a user in a room.
        """
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        if user_id not in self.active_connections[room_id]:
            self.active_connections[room_id][user_id] = []
        
        self.active_connections[room_id][user_id].append(websocket)
        logger.info(f"User {user_id} connected. Room: {room_id}. Total rooms: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, room_id: str, user_id: str):
        """
        Remove a specific connection for a user in a room.
        """
        logger.info(f"Disconnecting user {user_id} from room {room_id}")
        if room_id in self.active_connections:
            if user_id in self.active_connections[room_id]:
                if websocket in self.active_connections[room_id][user_id]:
                    self.active_connections[room_id][user_id].remove(websocket)
                
                if not self.active_connections[room_id][user_id]:
                    del self.active_connections[room_id][user_id]
            
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        
        logger.info(f"Connection removed for user {user_id} in room {room_id}. Room exists: {room_id in self.active_connections}")

    async def disconnect_user(self, room_id: str, user_id: str, reason: str = "Membership revoked"):
        """
        Forcefully disconnect all connections for a specific user in a room.
        """
        logger.info(f"Attempting to kick user {user_id} from room {room_id}")
        if room_id in self.active_connections:
            if user_id in self.active_connections[room_id]:
                connections = list(self.active_connections[room_id][user_id])
                logger.info(f"Found {len(connections)} connections for user {user_id} in {room_id}")
                for websocket in connections:
                    try:
                        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason)
                    except Exception as e:
                        logger.debug(f"Error closing WS during kick: {e}")
                    self.disconnect(websocket, room_id, user_id)
                logger.info(f"Kicked user {user_id} from room {room_id} connections")
            else:
                logger.debug(f"User {user_id} not found in room {room_id} active connections. Existing users: {list(self.active_connections[room_id].keys())}")
        else:
            logger.debug(f"Room {room_id} not found in active connections. Existing rooms: {list(self.active_connections.keys())}")

    async def broadcast(self, room_id: str, message: dict):
        """
        Send a message to all connected clients in a room.
        If Pub/Sub is enabled, publishes to Redis for cross-server distribution.
        Otherwise, broadcasts directly to local connections.
        """
        logger.info(f"Broadcasting message to room_id: {room_id}. PubSub enabled: {bool(self.pubsub)}")
        if self.pubsub:
            # Multi-server mode: publish to Redis
            channel = f"room:{room_id}"
            await self.pubsub.publish(channel, message)
        else:
            # Single-server mode: direct local broadcast
            await self._broadcast_local(room_id, message)

    async def _broadcast_local(self, room_id: str, message: dict):
        """
        Send a message to all local WebSocket connections in a room.
        This is called either directly (single-server) or by Pub/Sub subscriber (multi-server).
        """
        if room_id in self.active_connections:
            users_count = len(self.active_connections[room_id])
            logger.info(f"Broadcast local: Found {users_count} active users in room {room_id}")
            for user_id, connections in list(self.active_connections[room_id].items()):
                for websocket in list(connections):
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to user {user_id} in {room_id}: {e}")
                        self.disconnect(websocket, room_id, user_id)
        else:
            logger.info(f"Broadcast local: No active connections found for room {room_id}")


# Global manager instance
manager = ConnectionManager()
