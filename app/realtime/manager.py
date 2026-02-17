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
        # Maps group_id -> {user_id: [WebSocket]}
        self.active_connections: Dict[str, Dict[str, List[WebSocket]]] = {}
        self.pubsub = pubsub_manager  # Optional Redis Pub/Sub manager

    async def connect(self, websocket: WebSocket, group_id: str, user_id: str):
        """
        Register a new connection for a user in a group.
        """
        await websocket.accept()
        if group_id not in self.active_connections:
            self.active_connections[group_id] = {}
        if user_id not in self.active_connections[group_id]:
            self.active_connections[group_id][user_id] = []
        
        self.active_connections[group_id][user_id].append(websocket)
        logger.info(f"User {user_id} connected. Group: {group_id}. Total groups: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, group_id: str, user_id: str):
        """
        Remove a specific connection for a user in a group.
        """
        logger.info(f"Disconnecting user {user_id} from group {group_id}")
        if group_id in self.active_connections:
            if user_id in self.active_connections[group_id]:
                if websocket in self.active_connections[group_id][user_id]:
                    self.active_connections[group_id][user_id].remove(websocket)
                
                if not self.active_connections[group_id][user_id]:
                    del self.active_connections[group_id][user_id]
            
            if not self.active_connections[group_id]:
                del self.active_connections[group_id]
        
        logger.info(f"Connection removed for user {user_id} in group {group_id}. Group exists: {group_id in self.active_connections}")

    async def disconnect_user(self, group_id: str, user_id: str, reason: str = "Membership revoked"):
        """
        Forcefully disconnect all connections for a specific user in a group.
        """
        logger.info(f"Attempting to kick user {user_id} from group {group_id}")
        if group_id in self.active_connections:
            if user_id in self.active_connections[group_id]:
                connections = list(self.active_connections[group_id][user_id])
                logger.info(f"Found {len(connections)} connections for user {user_id} in {group_id}")
                for websocket in connections:
                    try:
                        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason)
                    except Exception as e:
                        logger.debug(f"Error closing WS during kick: {e}")
                    self.disconnect(websocket, group_id, user_id)
                logger.info(f"Kicked user {user_id} from group {group_id} connections")
            else:
                logger.debug(f"User {user_id} not found in group {group_id} active connections. Existing users: {list(self.active_connections[group_id].keys())}")
        else:
            logger.debug(f"Group {group_id} not found in active connections. Existing groups: {list(self.active_connections.keys())}")

    async def broadcast(self, group_id: str, message: dict):
        """
        Send a message to all connected clients in a group.
        If Pub/Sub is enabled, publishes to Redis for cross-server distribution.
        Otherwise, broadcasts directly to local connections.
        """
        logger.info(f"Broadcasting message to group_id: {group_id}. PubSub enabled: {bool(self.pubsub)}")
        if self.pubsub:
            # Multi-server mode: publish to Redis
            channel = f"group:{group_id}"
            await self.pubsub.publish(channel, message)
        else:
            # Single-server mode: direct local broadcast
            await self._broadcast_local(group_id, message)

    async def _broadcast_local(self, group_id: str, message: dict):
        """
        Send a message to all local WebSocket connections in a group.
        This is called either directly (single-server) or by Pub/Sub subscriber (multi-server).
        """
        if group_id in self.active_connections:
            users_count = len(self.active_connections[group_id])
            logger.info(f"Broadcast local: Found {users_count} active users in group {group_id}")
            for user_id, connections in list(self.active_connections[group_id].items()):
                for websocket in list(connections):
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to user {user_id} in {group_id}: {e}")
                        self.disconnect(websocket, group_id, user_id)
        else:
            logger.info(f"Broadcast local: No active connections found for group {group_id}")


# Global manager instance
manager = ConnectionManager()
