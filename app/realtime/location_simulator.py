"""
Live Location Simulator.
Generates fake GPS movement for testing.
"""
import asyncio
import logging
from datetime import datetime, timezone
import random
import uuid
from typing import Dict, Optional

from sqlalchemy import update, and_
from app.db.session import AsyncSessionLocal
from app.modules.location.service import LocationService
from app.modules.location.model import LiveLocation
from app.modules.location.schema import LocationUpdate

from app.core.exceptions import PermissionDeniedException, NotFoundException

from app.common.constants import (
    SIMULATOR_BASE_LAT,
    SIMULATOR_BASE_LNG,
    SIMULATOR_UPDATE_INTERVAL,
    SIMULATOR_DRIFT_DELTA,
    SIMULATOR_START_OFFSET
)

logger = logging.getLogger(__name__)


class LocationSimulator:
    """
    Manages background simulation tasks for users in events.
    """
    
    # Track active tasks: "event_id:user_id" -> Task
    _active_tasks: Dict[str, asyncio.Task] = {}

    @classmethod
    async def start_simulation(
        cls, 
        event_id: uuid.UUID, 
        user_id: uuid.UUID
    ) -> bool:
        """
        Start simulating movement for a user in an event.
        Returns True if started, False if already running.
        """
        key = f"{event_id}:{user_id}"
        
        if key in cls._active_tasks:
            task = cls._active_tasks[key]
            if not task.done():
                return False
        
        async with AsyncSessionLocal() as db:
            # If the event is not ONGOING or user not accepted, this will RAISE 
            # an exception, which the API router will catch and return to the user.
            # This prevents silent background failures.
            try:
                await LocationService._validate_permissions(db, event_id, user_id)
            except Exception as e:
                logger.warning(f"Simulator start rejected for {key}: {e}")
                raise e

            try:
                await db.execute(
                    update(LiveLocation)
                    .where(and_(LiveLocation.event_id == event_id, LiveLocation.user_id == user_id))
                    .values(is_active=True, last_updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to proactively activate location for {key}: {e}")

        # Start background task
        task = asyncio.create_task(
            cls._simulation_loop(event_id, user_id)
        )
        cls._active_tasks[key] = task
        logger.info(f"Started simulation for {key}")
        
        return True

    @classmethod
    async def stop_simulation(
        cls, 
        event_id: uuid.UUID, 
        user_id: uuid.UUID
    ) -> bool:
        """
        Stop simulation for a user.
        """
        key = f"{event_id}:{user_id}"
        task = cls._active_tasks.get(key)
        
        if task and not task.done():
            task.cancel()
            # The finally block in _simulation_loop will handle removal from _active_tasks
            return True
        
        # Even if task doesn't exist, ensure DB status is consistent if requested
        async with AsyncSessionLocal() as db:
            await LocationService.stop_sharing(db, event_id, user_id)
        
        return False

    @classmethod
    async def _simulation_loop(cls, event_id: uuid.UUID, user_id: uuid.UUID):
        """
        Background loop to generate coordinates.
        """
        key = f"{event_id}:{user_id}"
        logger.info(f"Simulation loop STARTED for {key}")
        
        # Start near base location with some random offset
        current_lat = SIMULATOR_BASE_LAT + random.uniform(-SIMULATOR_START_OFFSET, SIMULATOR_START_OFFSET)
        current_lng = SIMULATOR_BASE_LNG + random.uniform(-SIMULATOR_START_OFFSET, SIMULATOR_START_OFFSET)

        try:
            while True:
                async with AsyncSessionLocal() as db:
                    # We check if location exists and is INACTIVE. 
                    current_loc = await LocationService.get_user_location(db, event_id, user_id)
                    
                    if current_loc and not current_loc.is_active:
                         logger.info(f"Simulation stopped externally for {key}")
                         break

                    try:
                        update = LocationUpdate(
                            latitude=current_lat,
                            longitude=current_lng
                        )
                        await LocationService.update_location(
                            db, event_id, user_id, update
                        )
                        logger.debug(f"Simulated update for {key}: {current_lat}, {current_lng}")
                    except Exception as e:
                        logger.error(f"Simulation update failed for {key}: {e}")
                        # If the event or user is invalid, stop the simulation
                        if "404" in str(e) or "PermissionDenied" in str(e):
                            logger.info(f"Terminating simulator for {key} due to error: {e}")
                            break
                
                await asyncio.sleep(SIMULATOR_UPDATE_INTERVAL) 

                #  Move Logic (Random Walk)
                delta_lat = random.uniform(-SIMULATOR_DRIFT_DELTA, SIMULATOR_DRIFT_DELTA)
                delta_lng = random.uniform(-SIMULATOR_DRIFT_DELTA, SIMULATOR_DRIFT_DELTA)
                
                current_lat += delta_lat
                current_lng += delta_lng

        except asyncio.CancelledError:
            logger.info(f"Simulation task cancelled for {key}")
            raise
        except Exception as e:
            logger.error(f"Simulation loop crashed for {key}: {e}")
        finally:
            # Clean up task reference - thread safe removal
            cls._active_tasks.pop(key, None)
            
            # Ensure DB reflects that sharing has stopped
            async with AsyncSessionLocal() as db:
                try:
                    await LocationService.stop_sharing(db, event_id, user_id)
                except Exception as e:
                    logger.error(f"Failed to stop sharing in finally block for {key}: {e}")
            
            logger.info(f"Simulation loop cleaned up for {key}")
