from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from backend.storage.models import OBSOLETE_TRIGGERS, TRIGGERS, Base


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}")
        event.listen(self.engine, "connect", _enable_foreign_keys)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def init(self) -> None:
        """Create missing tables and triggers. Idempotent."""
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            for name in OBSOLETE_TRIGGERS:
                conn.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
            for ddl in TRIGGERS:
                conn.execute(text(ddl))

    def recreate(self) -> None:
        """Discard every table and start empty (the single-session workflow's reset). Tables are dropped
        rather than the file deleted: on Windows an open handle elsewhere would block the delete. Triggers go
        first, so the scope-lock guards do not block discarding the whole session."""
        with self.engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            for (name,) in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'")).all():
                conn.execute(text(f'DROP TRIGGER IF EXISTS "{name}"'))
            Base.metadata.drop_all(conn)
        with self.engine.connect() as conn:
            conn.execute(text("VACUUM"))
        self.engine.dispose()            # connections return with foreign keys on again
        self.init()

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A transaction: committed on success, rolled back on any exception."""
        with self._sessions() as session, session.begin():
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


def _enable_foreign_keys(dbapi_conn, _record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
