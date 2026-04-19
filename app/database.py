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
    import app.models  # noqa: F401

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
            conn.execute(
                text(
                    """
                    UPDATE owners
                    SET last_name = COALESCE(NULLIF(first_name, ''), 'User')
                    WHERE last_name IS NULL OR last_name = '';
                    """
                )
            )
            conn.execute(text("ALTER TABLE owners ALTER COLUMN zone_id SET NOT NULL;"))
            conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'accounttype') THEN
                            ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'private_plus';
                            ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'enhanced';
                            ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'enhanced_plus';
                        END IF;
                    END$$;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ownerrole') THEN
                            CREATE TYPE ownerrole AS ENUM ('administrator', 'user');
                        END IF;
                    END$$;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE owners
                    ADD COLUMN IF NOT EXISTS role ownerrole;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE owners
                    ADD COLUMN IF NOT EXISTS account_owner_id INTEGER;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE owners
                    SET role = 'administrator'
                    WHERE role IS NULL;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE owners
                    SET account_owner_id = id
                    WHERE account_owner_id IS NULL;
                    """
                )
            )
            conn.execute(text("ALTER TABLE owners ALTER COLUMN role SET NOT NULL;"))
            conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = 'fk_owners_account_owner'
                        ) THEN
                            ALTER TABLE owners
                            ADD CONSTRAINT fk_owners_account_owner
                            FOREIGN KEY (account_owner_id) REFERENCES owners(id) ON DELETE SET NULL;
                        END IF;
                    END$$;
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_owner_account_owner_id ON owners (account_owner_id);"))

            # Allow duplicate zone_id values across different owners.
            conn.execute(text("ALTER TABLE zones DROP CONSTRAINT IF EXISTS zones_zone_id_key;"))
            conn.execute(text("DROP INDEX IF EXISTS zones_zone_id_key;"))
            conn.execute(text("DROP INDEX IF EXISTS ix_zones_zone_id;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_zones_zone_id ON zones (zone_id);"))

            # Backward-compatible schema patch for older deployments missing member location fields.
            conn.execute(
                text(
                    """
                    ALTER TABLE member_locations
                    ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE member_locations
                    ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE member_locations
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW();
                    """
                )
            )


def drop_db():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)
