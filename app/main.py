from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from .auth import decode_access_token
from .routers import resources
from .routers import auth as auth_router
from .routers import admin as admin_router
from .routers import keys as keys_router
from .scheduler import check_reminders


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
