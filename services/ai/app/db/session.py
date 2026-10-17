from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

# Swap driver to asyncpg regardless of what's in the env file.
# psycopg2-binary is kept only for Alembic CLI migrations.
_db_url = make_url(settings.ai_database_url).set(drivername="postgresql+asyncpg")

engine = create_async_engine(_db_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI session dependency; override this one object in tests."""
    async with AsyncSessionLocal() as db:
        yield db
