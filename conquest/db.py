"""SQLite engine, sessions, and first-run setup."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from conquest import config
from conquest.categories import DEFAULT_DRIVE_LIMITS
from conquest.models import Base, Settings


def make_engine(db_path: Path | None = None) -> Engine:
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    # FastAPI runs sync routes in a thread pool, so connections must be
    # usable from threads other than the one that opened them.
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(engine)
    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.get(Settings, 1) is None:
            session.add(
                Settings(
                    id=1,
                    home_label=config.DEFAULT_HOME_LABEL,
                    home_lat=config.DEFAULT_HOME_LAT,
                    home_lng=config.DEFAULT_HOME_LNG,
                    drive_limits=dict(DEFAULT_DRIVE_LIMITS),
                    interest_profile=config.DEFAULT_INTEREST_PROFILE,
                    category_boosts={},
                )
            )
            session.commit()


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """A session that commits on success and rolls back on any error."""
    session = session_factory(engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_settings(session: Session) -> Settings:
    settings = session.get(Settings, 1)
    if settings is None:  # pragma: no cover - init_db always creates it
        raise RuntimeError("Settings row is missing; the database was not initialised.")
    return settings
