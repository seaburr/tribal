from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect, text

from .auth import decode_access_token
from .database import engine
from .models import Base
from .routers import resources
from .routers import auth as auth_router
from .routers import admin as admin_router
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


_run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "cron", minute=0)  # runs every hour; notify_hour configured in Admin
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Tribal", lifespan=lifespan)

# ── Auth middleware ────────────────────────────────────────────────────────────
# Paths that do NOT require a valid session cookie.
_AUTH_EXEMPT_PREFIXES = ("/auth/", "/static/")
_AUTH_EXEMPT_EXACT = {"/login", "/healthz"}


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in _AUTH_EXEMPT_EXACT:
        return await call_next(request)
    if any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
        return await call_next(request)

    token = request.cookies.get("session")
    if not token or decode_access_token(token) is None:
        if request.method == "GET":
            return RedirectResponse(url="/login", status_code=303)
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    return await call_next(request)


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(resources.router)
app.include_router(auth_router.router)
app.include_router(admin_router.router)
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
