# TrackUs 🚀

**TrackUs** is a modern, multi-tenant travel coordination platform backend built with FastAPI. It enables seamless trip planning, real-time coordination, and group communication for travelers and organizations.

---

##  Features

- ** Multi-tenancy**: Robust isolation for different organizations and groups.
- **⚡ Real-time Coordination**: Live location tracking and chat functionality via WebSockets.
- ** Secure Authentication**: JWT-based authentication with role-based access control (RBAC).
- ** Event Management**: Create, manage, and coordinate travel events and itineraries.
- ** Real-time Chat**: Group and event-specific communication channels.
- ** Location Tracking**: High-frequency location updates for better group visibility.
- ** Notifications**: Real-time alerts and system notifications.
- ** Background Tasks**: Async processing using Celery and Redis.
- ** Rate Limiting**: Built-in protection against API abuse.

---

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12+)
- **Database**: [PostgreSQL](https://www.postgresql.org/) with [SQLAlchemy](https://www.sqlalchemy.org/) (Async)
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Caching & Pub/Sub**: [Redis](https://redis.io/)
- **Task Queue**: [Celery](https://docs.celeryq.dev/)
- **Real-time**: [WebSockets](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **Authentication**: JWT (Jose, Passlib)

---

## 📂 Project Structure

```text
TrackUs/
├── alembic/              # Database migration scripts
├── app/
│   ├── common/           # Shared utilities and helpers
│   ├── core/             # Core logic (config, security, exceptions)
│   ├── db/               # Database session and model base
│   ├── dependencies/     # FastAPI dependencies
│   ├── modules/          # Domain-driven modules
│   │   ├── auth/         # Authentication & identity
│   │   ├── tenants/      # Organization management
│   │   ├── users/        # User profiles & management
│   │   ├── chat/         # Messaging systems
│   │   └── ...           # (events, groups, location, notifications)
│   ├── realtime/         # WebSocket managers and handlers
│   └── main.py           # Application entry point
├── scripts/              # Useful scripts (seeding, etc.)
└── pyproject.toml        # Dependency management (uv)
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL
- Redis
- [uv](https://github.com/astral-sh/uv) (recommended for package management)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd TrackUs
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Update .env with your local database and redis credentials
   ```

3. **Install dependencies**:
   ```bash
   uv sync
   # OR: pip install -r requirements.txt
   ```

4. **Run Migrations**:
   ```bash
   uv run alembic upgrade head
   ```

5. **Start the Application**:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

---

## Services

To run the background tasks and real-time features, ensure the following services are running:

### 1. Redis
```bash
redis-server
```

### 2. Celery Worker
```bash
uv run celery -A app.core.celery_app worker --loglevel=info
```

### 3. Celery Beat
```bash
uv run celery -A app.core.celery_app beat --loglevel=info
```

---

##  Real-time Capabilities

TrackUs uses Redis Pub/Sub for scalable WebSocket management. Current endpoints include:

- `/chat/groups/{group_id}`: Group messaging
- `/chat/events/{event_id}`: Event-specific chat
- `/events/{event_id}/location`: Real-time location sharing
- `/notifications`: Live system alerts

---

##  API Documentation

Once the server is running, you can access the interactive documentation:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

