"""
WebSocket handlers for live location.
"""
import json
import logging
import uuid
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect, Query, status
from pydantic import ValidationError

from app.db.session import AsyncSessionLocal
from app.modules.location.service import LocationService
from app.modules.location.schema import LocationUpdate
from app.realtime.chat import get_ws_user
from app.realtime.manager import manager
from app.core.exceptions import PermissionDeniedException, BadRequestException

logger = logging.getLogger(__name__)


async def location_socket_handler(
    websocket: WebSocket,
    event_id: uuid.UUID,
    token: str = Query(...)
):
    """
    WebSocket handler for event live location.
    Path: /events/{event_id}/location
    """
    await websocket.accept()
    user = await get_ws_user(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    room_id = str(event_id)
    
    # We use LocationService._validate_permissions which checks Participant status and Event status
    async with AsyncSessionLocal() as db:
        try:
            await LocationService._validate_permissions(db, event_id, user.id, user.tenant_id)
        except Exception as e:
            logger.error(f"WS Location connection validation failed for event {event_id}: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # Connect to Manager
    # reuse event_id as room_id for broadcasting location updates to the same channel
    await manager.connect(websocket, room_id, str(user.id))

    try:
        while True:
            # Listen for location updates
            data_text = await websocket.receive_text()
            
            if not data_text.strip():
                continue
            
            try:
                data = json.loads(data_text)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type")

            async with AsyncSessionLocal() as db:
                if msg_type == "location_update":
                    try:
                        loc_update = LocationUpdate(
                            latitude=data.get("latitude"),
                            longitude=data.get("longitude")
                        )
                        
                        await LocationService.update_location(
                            db, event_id, user.id, user.tenant_id, loc_update
                        )
                    except ValidationError as e:
                        await websocket.send_json({"type": "error", "message": str(e)})
                    except (PermissionDeniedException, BadRequestException) as e:
                        await websocket.send_json({"type": "error", "message": e.detail})

                    except Exception as e:
                        logger.error(f"Location update error: {e}")
                
                elif msg_type == "stop_sharing":
                    await LocationService.stop_sharing(db, event_id, user.id, user.tenant_id)
                
                else:
                    logger.debug(f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:

        manager.disconnect(websocket, room_id, str(user.id))
        logger.info(f"User {user.id} disconnected from location stream {event_id}")
    except Exception as e:
        logger.error(f"WS Location Link error in event {event_id}: {e}")
        manager.disconnect(websocket, room_id, str(user.id))
