"""
Shared constants for the application.
"""

# Location Simulator Constants
SIMULATOR_BASE_LAT = 12.9716  # Default Latitude
SIMULATOR_BASE_LNG = 77.5946  # Default Longitude 
SIMULATOR_UPDATE_INTERVAL = 2  # Seconds between location updates
SIMULATOR_DRIFT_DELTA = 0.0005  # Maximum change in lat/lng per update
SIMULATOR_START_OFFSET = 0.01   # Random offset from base location at start

# Notification Constants
class NotificationType:
    EVENT_INVITED = "event.invited"
    EVENT_STARTED = "event.started"
    EVENT_CANCELLED = "event.cancelled"
    EVENT_JOINED = "event.joined"
    EVENT_LEFT = "event.left"
    MEMBER_REMOVED = "member.removed"
    GROUP_ADDED = "group.added"
    PARTICIPANT_ADDED = "participant.added"
    PARTICIPANT_REMOVED = "participant.removed"

class ReferenceType:
    EVENT = "event"
    GROUP = "group"
    USER = "user"

# Rate Limit Constants
RATE_LIMIT_AUTH_TIMES = 5
RATE_LIMIT_AUTH_SECONDS = 60
RATE_LIMIT_REFRESH_TIMES = 10
