# TrackUs Backend

Multi-tenant travel coordination platform backend built with FastAPI.

## Features

- ✅ Multi-tenant architecture with strict data isolation
- ✅ Role-based access control (SUPER_ADMIN, TENANT_ADMIN, USER)
- ✅ JWT authentication with access and refresh tokens
- ✅ Email verification flow
- ✅ Async PostgreSQL with SQLAlchemy 2.0
- ✅ RESTful API with automatic documentation
- ✅ Background task processing

## Technology Stack

- **Python 3.12+**
- **FastAPI** - Modern web framework
- **SQLAlchemy 2.0** - Async ORM
- **PostgreSQL** - Database
- **Pydantic v2** - Data validation
- **Alembic** - Database migrations
- **JWT** - Authentication
- **uv** - Package management

## Project Structure

```
TrackUs/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── core/                   # Core utilities
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   └── email.py
│   ├── db/                     # Database configuration
│   │   ├── base.py
│   │   └── session.py
│   ├── dependencies/           # Reusable dependencies
│   │   ├── auth.py
│   │   └── tenant.py
│   ├── common/                 # Shared utilities
│   │   ├── enums.py
│   │   ├── mixins.py
│   │   └── schemas.py
│   └── modules/                # Feature modules
│       ├── auth/
│       ├── tenants/
│       └── users/
├── alembic/                    # Database migrations
├── scripts/                    # Utility scripts
└── tests/                      # Test files
```

## Setup Instructions

### Prerequisites

- Python 3.12+
- Docker (for PostgreSQL)
- uv package manager

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and Setup

```bash
cd /Users/AdityaGoswami/Phase-2-vertical/milestone-4-project/TrackUs

# Install dependencies
uv sync

# Copy environment file
cp .env.example .env
```

### 3. Start PostgreSQL

```bash
docker-compose up -d
```

### 4. Run Migrations

```bash
# Initialize Alembic (if not already done)
uv run alembic init alembic

# Create initial migration
uv run alembic revision --autogenerate -m "Initial schema"

# Apply migrations
uv run alembic upgrade head
```

### 5. Seed Super Admin

```bash
uv run python scripts/seed_superadmin.py
```

**Default Super Admin Credentials:**
- Email: `superadmin@trackus.com`
- Password: `SuperAdmin@123`

⚠️ **Change this password immediately in production!**

### 6. Run the Application

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication

- `POST /api/v1/auth/login` - Login and get tokens
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user info

### Tenants (SUPER_ADMIN only)

- `POST /api/v1/tenants` - Create tenant
- `GET /api/v1/tenants` - List tenants
- `GET /api/v1/tenants/{id}` - Get tenant
- `PATCH /api/v1/tenants/{id}` - Update tenant
- `DELETE /api/v1/tenants/{id}` - Delete tenant

### Users

- `POST /api/v1/users` - Create user (SUPER_ADMIN/TENANT_ADMIN)
- `GET /api/v1/users/verify` - Verify email (public)
- `GET /api/v1/users` - List users
- `GET /api/v1/users/{id}` - Get user
- `PATCH /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user

## Authentication Flow

### 1. Super Admin Creates Tenant

```bash
POST /api/v1/tenants
Authorization: Bearer <super_admin_token>
{
  "name": "Acme Corp",
  "description": "Travel agency"
}
```

### 2. Super Admin Creates Tenant Admin

```bash
POST /api/v1/users
Authorization: Bearer <super_admin_token>
{
  "email": "admin@acme.com",
  "password": "Admin@123",
  "first_name": "John",
  "last_name": "Doe",
  "role": "TENANT_ADMIN",
  "tenant_id": "<tenant_id>"
}
```

A verification email will be sent (logged to console in development).

### 3. Tenant Admin Verifies Email

```bash
GET /api/v1/users/verify?token=<verification_token>
```

### 4. Tenant Admin Logs In

```bash
POST /api/v1/auth/login
{
  "email": "admin@acme.com",
  "password": "Admin@123"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### 5. Tenant Admin Creates Users

```bash
POST /api/v1/users
Authorization: Bearer <tenant_admin_token>
{
  "email": "user@acme.com",
  "password": "User@123",
  "first_name": "Jane",
  "last_name": "Smith",
  "role": "USER"
}
```

## Token Management

- **Access Token**: Expires in 30 minutes
- **Refresh Token**: Expires in 30 days

To refresh an access token:

```bash
POST /api/v1/auth/refresh
{
  "refresh_token": "<refresh_token>"
}
```

## Email Verification

In development mode, emails are logged to the console. Look for output like:

```
================================================================================
📧 EMAIL (Development Mode)
To: admin@acme.com
Subject: Verify your TrackUs account
Body:
Hello John,

Welcome to TrackUs! Please verify your email address by clicking the link below:

http://localhost:8000/api/v1/users/verify?token=eyJ...

This link will expire in 24 hours.
================================================================================
```

## Tenant Isolation

- **SUPER_ADMIN**: Can access all tenants
- **TENANT_ADMIN**: Can only access their own tenant
- **USER**: Can only access their own tenant

All user operations enforce strict tenant boundaries to prevent data leakage.

## Development

### Run with auto-reload

```bash
uv run uvicorn app.main:app --reload
```

### Create a new migration

```bash
uv run alembic revision --autogenerate -m "Description"
```

### Apply migrations

```bash
uv run alembic upgrade head
```

### Rollback migration

```bash
uv run alembic downgrade -1
```

## Testing

```bash
# Run tests (coming soon)
uv run pytest
```

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - Secret key for JWT tokens
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Access token expiration (default: 30)
- `REFRESH_TOKEN_EXPIRE_DAYS` - Refresh token expiration (default: 30)

## Next Steps

Phase 1 (Current):
- ✅ Authentication & User Management
- ✅ Tenant Management
- ✅ Email Verification

Phase 2 (Upcoming):
- Groups & Group Membership
- Travel Events
- Event Participants

Phase 3 (Upcoming):
- Real-time Chat (WebSocket)
- Live Location Tracking
- Notifications

## License

Proprietary
