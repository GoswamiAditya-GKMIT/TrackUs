
import logging
from fastapi import WebSocket, WebSocketDisconnect, Query, status, APIRouter

from app.realtime.chat import get_ws_user
from app.realtime.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/notifications")
async def notification_socket_handler(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket endpoint for real-time notifications.
    Client connects to receive updates instantly.
    """
    user = await get_ws_user(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    user_channel = f"user:{user.id}"
    
    await manager.connect(websocket, user_channel, str(user.id))
    
    try:
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_channel, str(user.id))
        logger.info(f"User {user.id} disconnected from notification stream")
    except Exception as e:
        logger.error(f"WS Notification error for user {user.id}: {e}")
        manager.disconnect(websocket, user_channel, str(user.id))
