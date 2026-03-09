# API Design Patterns

## Middleware Chain

Requests flow through middleware in order. Each middleware can modify the request, the response, or short-circuit the chain entirely.

```
Request →  PrometheusMiddleware  →  RateLimitMiddleware  →  CORSMiddleware  →  Router
              (metrics)               (429 if exceeded)      (CORS headers)    (handler)
Response ←       ←                        ←                      ←               ←
```

**Order matters.** Prometheus is outermost so it captures ALL requests (including rate-limited ones). Rate limiting is before CORS so rejected requests don't get CORS headers.

## Dependency Injection (FastAPI)

FastAPI uses `Depends()` to inject shared resources into route handlers:

```python
@router.get("/api/trades")
async def list_trades(
    db: Annotated[AsyncSession, Depends(get_db)],           # DB session
    user: Annotated[User, Depends(get_current_user)],       # Auth check
):
```

`get_db` creates a session, yields it, then cleans up after the handler returns. `get_current_user` validates the JWT, loads the user, and raises 401 if invalid.

This means: if `get_current_user` is in the signature, the route is automatically authenticated. No decorator needed, no manual token checking.

## Service Layer Pattern

```
Router (HTTP concerns) → Service (business logic) → Repository (data access)
```

Routers parse HTTP requests and return HTTP responses. Services contain reusable business logic. Repositories handle database queries.

```python
# Router — thin, handles HTTP
@router.get("/api/users")
async def list_users(db, user):
    return await user_service.list_users(db)

# Service — business logic
async def list_users(db):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()
```

Why separate? If you need the same logic in a CLI command, a background task, or another route, you call the service function directly — no HTTP involved.

## REST Conventions

| Method | Path | Action | Status |
|---|---|---|---|
| GET | /api/users | List all | 200 |
| GET | /api/users/{id} | Get one | 200 or 404 |
| POST | /api/users | Create | 201 |
| PUT | /api/users/{id} | Full update | 200 |
| PATCH | /api/users/{id} | Partial update | 200 |
| DELETE | /api/users/{id} | Delete | 204 |

FastAPI generates OpenAPI docs automatically at `/docs` (Swagger UI) and `/redoc`.

## Deep Dive

- FastAPI docs: https://fastapi.tiangolo.com/
- Pydantic v2: https://docs.pydantic.dev/latest/
- OpenAPI spec: https://spec.openapis.org/oas/v3.1.0
- Martin Fowler on Dependency Injection: https://martinfowler.com/articles/injection.html
