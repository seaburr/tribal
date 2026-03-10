import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/tribal.db")

_sqlite = DATABASE_URL.startswith("sqlite")


def _connect_args() -> dict:
    """Build driver-level connection arguments.

    For MySQL, SSL is configured via environment variables rather than the
    DATABASE_URL so that cert file paths and sensitive options stay out of
    connection strings / logs.

    Supported env vars (MySQL only):
      DB_SSL_CA   — path to the CA certificate file (e.g. DO managed MySQL CA)
      DB_SSL_CERT — path to the client certificate file (mutual TLS)
      DB_SSL_KEY  — path to the client private key file (mutual TLS)
      DB_SSL_REQUIRE — set to "true" to require encrypted connections without
                       a specific CA cert (e.g. self-signed / internal CAs)
    """
    if _sqlite:
        return {"check_same_thread": False}

    ssl: dict = {}
    if ca := os.environ.get("DB_SSL_CA"):
        ssl["ca"] = ca
    if cert := os.environ.get("DB_SSL_CERT"):
        ssl["cert"] = cert
    if key := os.environ.get("DB_SSL_KEY"):
        ssl["key"] = key

    require = os.environ.get("DB_SSL_REQUIRE", "").lower() in ("1", "true", "yes")
    if ssl or require:
        return {"ssl": ssl}  # empty dict = encrypt but skip cert verification

    return {}


engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args(),
    pool_pre_ping=not _sqlite,
    pool_recycle=1800 if not _sqlite else -1,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
