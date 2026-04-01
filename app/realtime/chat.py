"""
WebSocket handlers for group chat.
"""
import json
import logging
import uuid
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.users.model import User

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
from app.modules.events.service import EventService
from app.modules.chat.service import EventChatService
from app.common.enums import ParticipantStatus




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
    await websocket.accept()
    user = await get_ws_user(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    room_id = str(group_id)
    
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
    await manager.connect(websocket, room_id, str(user.id))

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
                    await manager.broadcast(room_id, payload)
                except PermissionDeniedException as e:
                    logger.warning(f"Permission denied for user {user.id} in group {group_id}: {e.detail}")
                    await websocket.send_json({"type": "error", "message": e.detail})
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
                except Exception as e:
                    logger.error(f"WS Message persistence error: {e}")
                    await websocket.send_json({"type": "error", "message": "Failed to send message"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id, str(user.id))
        logger.info(f"User {user.id} disconnected from group {group_id}")
    except Exception as e:
        logger.error(f"WS Link error: {e}")
        manager.disconnect(websocket, room_id, str(user.id))


async def event_chat_socket_handler(
    websocket: WebSocket,
    event_id: uuid.UUID,
    token: str = Query(...)
):
    """
    WebSocket handler for event chat.
    Path: /chat/events/{event_id}
    """
    await websocket.accept()
    user = await get_ws_user(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    room_id = str(event_id)
    
    # 2. Validate Participant Status & Tenant
    async with AsyncSessionLocal() as db:
        try:
            # We must check if user is an ACCEPTED participant
            participant = await EventService._get_participant(db, event_id, user.id)
            if not participant or participant.status != ParticipantStatus.ACCEPTED:
                 await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                 return
        except Exception as e:
            logger.error(f"WS Connection validation failed for event {event_id}: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # 3. Connect to Manager (using event_id as the room key)
    # The manager is generic, so we can use event_id as room_id
    await manager.connect(websocket, room_id, str(user.id))

    try:
        while True:
            # 4. Listen for messages
            message_text = await websocket.receive_text()
            
            if not message_text.strip():
                continue
            
            async with AsyncSessionLocal() as db:
                msg_create = ChatMessageCreate(message=message_text)
                try:
                    message = await EventChatService.create_message(
                        db, event_id, user, msg_create
                    )
                    # 5. Broadcast to all members
                    payload = EventChatService.get_broadcast_payload(message)
                    await manager.broadcast(room_id, payload)
                except PermissionDeniedException as e:
                    logger.warning(f"Permission denied for user {user.id} in event {event_id}: {e.detail}")
                    await websocket.send_json({"type": "error", "message": e.detail})
                except Exception as e:
                    logger.error(f"WS Message persistence error in event {event_id}: {e}")
                    await websocket.send_json({"type": "error", "message": "Failed to send message"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id, str(user.id))
        logger.info(f"User {user.id} disconnected from event {event_id}")
    except Exception as e:
        logger.error(f"WS Link error in event {event_id}: {e}")
        manager.disconnect(websocket, room_id, str(user.id))
