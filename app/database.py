"""Database connection and session management."""
# UPDATED for Zoning-Messaging-System-Summary-v1.1.pdf
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
        if engine.dialect.name == "postgresql":
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            # Backward-compatible schema patch for older deployments missing owners.zone_id.
            conn.execute(text("ALTER TABLE owners ADD COLUMN IF NOT EXISTS zone_id VARCHAR(100);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_owner_zone_id ON owners (zone_id);"))
            conn.execute(
                text(
                    """
                    UPDATE owners
                    SET zone_id = CONCAT('owner-', id::text)
                    WHERE zone_id IS NULL OR zone_id = '';
                    """
                )
            )
            conn.execute(text("ALTER TABLE owners ALTER COLUMN zone_id SET NOT NULL;"))
            conn.execute(
                text(
                    """
                    ALTER TABLE owners
                    ALTER COLUMN account_type TYPE VARCHAR(32)
                    USING account_type::text;
                    """
                )
            )

            # Allow duplicate zone_id values across different owners.
            conn.execute(text("ALTER TABLE zones DROP CONSTRAINT IF EXISTS zones_zone_id_key;"))
            conn.execute(text("DROP INDEX IF EXISTS zones_zone_id_key;"))
            conn.execute(text("DROP INDEX IF EXISTS ix_zones_zone_id;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_zones_zone_id ON zones (zone_id);"))
            conn.execute(
                text(
                    """
                    ALTER TABLE zones
                    ALTER COLUMN zone_type TYPE VARCHAR(64)
                    USING zone_type::text;
                    """
                )
            )

            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(32);"))
            conn.execute(text("UPDATE messages SET message_type = 'Private' WHERE message_type IS NULL AND visibility::text = 'PRIVATE';"))
            conn.execute(text("UPDATE messages SET message_type = 'PA' WHERE message_type IS NULL;"))
            conn.execute(text("DROP INDEX IF EXISTS ix_message_visibility_created;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_message_type_created ON messages (message_type, created_at);"))
            conn.execute(text("ALTER TABLE messages ALTER COLUMN message_type SET NOT NULL;"))


def drop_db():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)
