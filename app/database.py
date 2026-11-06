"""
Database configuration and session management for SpendSentinel.

Uses SQLite with SQLAlchemy ORM to provide secure, parameterized persistence.
"""

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv(
    "SENTINEL_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./sentinel.db")
)

# SQLite requires check_same_thread=False for multi-threaded FastAPI access
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy session per request.
    Ensures safe session closure after request handling.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
