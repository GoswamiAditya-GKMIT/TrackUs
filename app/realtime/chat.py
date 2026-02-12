"""
WebSocket handlers for group chat.
"""
import json
import logging
import uuid
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.security import decode_access_token
from app.modules.users.service import UserService
from app.modules.chat.service import ChatService
from app.modules.chat.schema import ChatMessageCreate
from app.realtime.manager import manager
from app.core.exceptions import AuthenticationException, PermissionDeniedException
from app.modules.groups.service import GroupService
from app.modules.groups.service import MembershipService



logger = logging.getLogger(__name__)


async def get_ws_user(token: str) -> Optional["User"]:
    """
    Authenticate user for WebSocket connection.
    """
    async with AsyncSessionLocal() as db:
        payload = decode_access_token(token)
        if not payload:
            return None
        
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
            
        try:
            user_id = uuid.UUID(user_id_str)
            user = await UserService.get_user(db, user_id)
            if not user.is_active or not user.is_email_verified:
                return None
            return user
        except Exception:
            return None


async def chat_socket_handler(
    websocket: WebSocket,
    group_id: uuid.UUID,
    token: str = Query(...)
):
    """
    WebSocket handler for group chat.
    Path: /chat/groups/{group_id}
    """
    user = await get_ws_user(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    group_id_str = str(group_id)
    
    # 2. Validate Membership & Tenant
    # Using AsyncSessionLocal directly for dependency-less validation
    async with AsyncSessionLocal() as db:
        try:
            # Reusing ChatService logic (which calls MembershipService)
            # We don't need to return anything, just check if it raises
            await GroupService.get_group(db, group_id, user)
            
            membership = await MembershipService.get_membership(db, group_id, user.id)
            if not membership or membership.left_at is not None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        except Exception as e:
            logger.error(f"WS Connection validation failed: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # 3. Connect to Manager
    await manager.connect(websocket, group_id_str, str(user.id))

    try:
        while True:
            # 4. Listen for messages
            message_text = await websocket.receive_text()
            
            if not message_text.strip():
                continue
            
            async with AsyncSessionLocal() as db:
                msg_create = ChatMessageCreate(message=message_text)
                try:
                    message = await ChatService.create_message(
                        db, group_id, user, msg_create
                    )
                    # 5. Broadcast to all members
                    payload = ChatService.get_broadcast_payload(message)
                    await manager.broadcast(group_id_str, payload)
                except PermissionDeniedException as e:
                    logger.warning(f"Permission denied for user {user.id} in group {group_id}: {e.detail}")
                    await websocket.send_json({"type": "error", "message": e.detail})
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
                except Exception as e:
                    logger.error(f"WS Message persistence error: {e}")
                    await websocket.send_json({"type": "error", "message": "Failed to send message"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, group_id_str, str(user.id))
        logger.info(f"User {user.id} disconnected from group {group_id}")
    except Exception as e:
        logger.error(f"WS Link error: {e}")
        manager.disconnect(websocket, group_id_str, str(user.id))
