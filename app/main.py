from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect, text

from .database import engine
from .models import Base
from .routers import resources
from .scheduler import check_reminders

Path("data").mkdir(exist_ok=True)
Base.metadata.create_all(bind=engine)


def _run_migrations():
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("resources")}
    with engine.connect() as conn:
        if "type" not in existing:
            conn.execute(text("ALTER TABLE resources ADD COLUMN type VARCHAR NOT NULL DEFAULT 'Other'"))
            conn.commit()


_run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "cron", hour=9, minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Tribal", lifespan=lifespan)
app.include_router(resources.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")
