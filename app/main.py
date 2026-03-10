import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from .auth import decode_access_token
from .routers import resources
from .routers import auth as auth_router
from .routers import admin as admin_router
from .routers import keys as keys_router
from .scheduler import check_reminders

BUILD_SHA = os.environ.get("BUILD_SHA", "dev")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "cron", minute=0)  # runs every hour; notify_hour configured in Admin
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Tribal", lifespan=lifespan)
Instrumentator().instrument(app)  # .expose() intentionally omitted — see /metrics below

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


def _versioned_html(path: str) -> HTMLResponse:
    """Serve an HTML file with versioned asset URLs and no-cache headers.

    Appends ?v=<BUILD_SHA> to all /static/*.css and /static/*.js href/src
    attributes so browsers fetch fresh assets after each deployment.
    The HTML itself gets Cache-Control: no-cache so the version stamp is
    always current without forcing a full re-download every time.
    """
    content = Path(path).read_text()
    content = re.sub(
        r'((?:href|src)="/static/[^"]+\.(?:css|js))"',
        rf'\1?v={BUILD_SHA}"',
        content,
    )
    return HTMLResponse(content, headers={"Cache-Control": "no-cache, must-revalidate"})


_CONST_LABELS = {"app_name": "tribal"}


class _LabelledRegistry:
    """Wraps a CollectorRegistry and injects constant labels into every sample."""

    def collect(self):
        for metric in REGISTRY.collect():
            metric.samples = [
                s._replace(labels={**s.labels, **_CONST_LABELS})
                for s in metric.samples
            ]
            yield metric


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(_LabelledRegistry()), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


@app.get("/login", include_in_schema=False)
def login_page():
    return _versioned_html("static/login.html")


@app.get("/")
def root():
    return _versioned_html("static/index.html")
