# FastAPI Template

Production-ready FastAPI backend with session-based auth, RBAC, and a clean layered architecture. Use this as a starting point — user management, authentication, and authorization are already done. Just add your business modules.

---

## Architecture

```
API Layer       (users/api.py)         — endpoints, request validation
Service Layer   (users/service.py)     — business logic
Repository Layer(users/repository.py)  — all database queries
Database        (SQLAlchemy + Alembic)
```

## Project Structure

```
fastapi-template/
├── users/
│   ├── api.py             # endpoints
│   ├── service.py         # business logic
│   ├── repository.py      # DB queries
│   ├── models.py          # SQLAlchemy models
│   ├── schema.py          # Pydantic schemas
│   ├── dependencies.py    # get_current_user, require_role, require_permission
│   ├── permissions.py     # permission name constants
│   ├── session_service.py # session create/validate/revoke
│   ├── security.py        # re-exports hash_password, verify_password
│   └── exceptions.py      # re-exports AppException
├── middleware/
│   ├── request_logging.py # request ID + logging
│   └── security.py        # security headers
├── utils/
│   ├── exceptions.py      # AppException
│   ├── security.py        # password hashing, session token hashing
│   └── models.py          # BaseModel (created_at, updated_at, is_active)
├── alembic/               # database migrations
├── main.py
├── config.py
├── database.py
├── requirements.txt
└── .env.example
```

---

## Setup

**1. Clone and create virtual environment**
```bash
python -m venv env
source env/bin/activate        # macOS / Linux
env\Scripts\activate           # Windows
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Set up environment variables**
```bash
cp .env.example .env
# Edit .env and set your DATABASE_URL
```

**4. Run database migrations**
```bash
cd fastapi-template
alembic upgrade head
```

**5. Start the server**
```bash
uvicorn main:app --reload
```

API docs available at: `http://localhost:8000/docs`

---

## Authentication

Session-based — no JWT.

| Endpoint | Description |
|---|---|
| `POST /users/register` | Create account |
| `POST /users/login` | Login — sets `session_id` cookie |
| `POST /users/logout` | Logout current session |
| `POST /users/logout-all` | Logout all devices |
| `GET  /users/profile` | Get current user |
| `PATCH /users/profile` | Update profile |
| `POST /users/change-password` | Change password |

---

## Authorization (RBAC)

```python
from users.dependencies import get_current_user, require_role, require_permission

# Any logged-in user
@router.get("/something")
def view(current_user = Depends(get_current_user)):
    ...

# Only users with the "admin" role
@router.delete("/something")
def delete(current_user = Depends(require_role("admin"))):
    ...

# Only users with a specific permission
@router.post("/something")
def action(current_user = Depends(require_permission("user.delete"))):
    ...
```

Permission constants are in `users/permissions.py`.

---

## Adding a New Module

1. Create `yourmodule/` folder with `api.py`, `service.py`, `repository.py`, `models.py`, `schema.py`
2. Import and register your router in `main.py`:
   ```python
   from yourmodule.api import your_router
   app.include_router(your_router)
   ```
3. Import your models in `alembic/env.py` so Alembic detects them:
   ```python
   from yourmodule import models
   ```
4. Generate and run migration:
   ```bash
   alembic revision --autogenerate -m "add yourmodule tables"
   alembic upgrade head
   ```

---

## Error Format

All errors return:
```json
{
  "success": false,
  "message": "Username already exists",
  "error_code": "USERNAME_TAKEN"
}
```

Raise from anywhere:
```python
from utils.exceptions import AppException

raise AppException("Username already exists", status_code=422, error_code="USERNAME_TAKEN")
```
