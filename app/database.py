"""Database connection and session management."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from app.core.config import settings

_db_url = settings.DATABASE_URL

# Create sync engine
engine = create_engine(
    _db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Create session factory
session_maker = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for models
Base = declarative_base()


def get_db() -> Session:
    """Dependency: get database session."""
    db = session_maker()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)
