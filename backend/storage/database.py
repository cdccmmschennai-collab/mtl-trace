from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from backend.storage.models import TRIGGERS, Base


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.engine = create_engine(f"sqlite:///{path.as_posix()}")
        event.listen(self.engine, "connect", _enable_foreign_keys)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def init(self) -> None:
        """Create missing tables and triggers. Idempotent."""
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            for ddl in TRIGGERS:
                conn.execute(text(ddl))

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
