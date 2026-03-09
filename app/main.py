from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from sqlalchemy import inspect, text

from .auth import decode_access_token
from .database import engine
from .models import Base
from .routers import resources
from .routers import auth as auth_router
from .routers import admin as admin_router
from .routers import keys as keys_router
from .scheduler import check_reminders

Path("data").mkdir(exist_ok=True)
Base.metadata.create_all(bind=engine)


def _run_migrations():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.connect() as conn:
        if "resources" in tables:
            existing = {c["name"] for c in inspector.get_columns("resources")}
            if "type" not in existing:
                conn.execute(text("ALTER TABLE resources ADD COLUMN type VARCHAR NOT NULL DEFAULT 'Other'"))
                conn.commit()
            if "deleted_at" not in existing:
                conn.execute(text("ALTER TABLE resources ADD COLUMN deleted_at DATETIME"))
                conn.commit()
            if "team_id" not in existing:
                conn.execute(text("ALTER TABLE resources ADD COLUMN team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL"))
                conn.commit()

        if "admin_settings" in tables:
            existing = {c["name"] for c in inspector.get_columns("admin_settings")}
            if "slack_webhook" not in existing:
                conn.execute(text("ALTER TABLE admin_settings ADD COLUMN slack_webhook VARCHAR"))
                conn.commit()
            if "alert_on_overdue" not in existing:
                conn.execute(text("ALTER TABLE admin_settings ADD COLUMN alert_on_overdue BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
            if "org_name" not in existing:
                conn.execute(text("ALTER TABLE admin_settings ADD COLUMN org_name VARCHAR"))
                conn.commit()

        if "users" in tables:
            existing = {c["name"] for c in inspector.get_columns("users")}
            if "is_admin" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
                # Promote the oldest user to admin if none exist yet
                result = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_admin = 1")).fetchone()
                if result[0] == 0:
                    conn.execute(text("UPDATE users SET is_admin = 1 WHERE id = (SELECT MIN(id) FROM users)"))
                    conn.commit()
            if "is_account_creator" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_account_creator BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
                # Mark the oldest user as the account creator
                conn.execute(text("UPDATE users SET is_account_creator = 1 WHERE id = (SELECT MIN(id) FROM users)"))
                conn.commit()


_run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "cron", minute=0)  # runs every hour; notify_hour configured in Admin
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Tribal", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, include_in_schema=False)

# ── Auth middleware ────────────────────────────────────────────────────────────
# Paths that do NOT require a valid session cookie.
_AUTH_EXEMPT_PREFIXES = ("/auth/",)
_AUTH_EXEMPT_EXACT = {"/login", "/healthz", "/metrics", "/static/tribal_logo.png", "/static/favicon.ico"}


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in _AUTH_EXEMPT_EXACT:
        return await call_next(request)
    if any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
        return await call_next(request)

    # 1. Session cookie
    token = request.cookies.get("session")
    if token and decode_access_token(token) is not None:
        return await call_next(request)

    # 2. Bearer API key — pass through; the route dependency validates the key
    #    and returns 401 (not a redirect) for invalid/revoked keys, which is
    #    the correct behaviour for programmatic clients.
    if request.headers.get("Authorization", "").startswith("Bearer "):
        return await call_next(request)

    if request.method == "GET":
        return RedirectResponse(url="/login", status_code=303)
    return JSONResponse(status_code=401, content={"detail": "Not authenticated"})


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(resources.router)
app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(keys_router.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse("static/login.html")


@app.get("/")
def root():
    return FileResponse("static/index.html")
