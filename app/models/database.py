"""SQLAlchemy database configuration with async SQLite."""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,
    future=True,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    import app.models.agent  # noqa: F401
    import app.models.audit  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
