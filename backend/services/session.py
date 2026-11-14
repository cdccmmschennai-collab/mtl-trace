"""The single working session of the tool: one finalized tag scope, one processing run, no history.

Starting a session with a scope workbook discards everything from before (database and stored files), then
creates the milestone, imports and locks the scope, and opens its one run. The milestone and run remain the
engine's internal structure — the scope stays authoritative and locked for the whole session — but the user
never manages them.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import PurePath

from sqlalchemy import select

from backend.domain.milestone import validate_milestone_code
from backend.services.milestones import MilestoneService, MilestoneView, ScopeRejectedError, ScopeReport
from backend.services.runs import RunDetailView, RunService
from backend.storage.database import Database
from backend.storage.files import FileStore
from backend.storage.models import Milestone, ProcessingRun

log = logging.getLogger(__name__)

DEFAULT_CODE = "MTL-SCOPE"


@dataclass(frozen=True)
class SessionView:
    milestone: MilestoneView
    run: RunDetailView


def code_from_file_name(file_name: str) -> str:
    """A filesystem-safe milestone code derived from the scope workbook's name (it names a data folder and
    appears in the generated workbook's title)."""
    stem = PurePath(file_name).stem.upper()
    code = re.sub(r"[^A-Z0-9._-]", "", re.sub(r"\s+", "-", stem))
    code = re.sub(r"-{2,}", "-", code).lstrip("._-")[:64].rstrip(".")
    return code if code and validate_milestone_code(code) is None else DEFAULT_CODE


class SessionService:
    def __init__(self, db: Database, files: FileStore, milestones: MilestoneService, runs: RunService):
        self.db = db
        self.files = files
        self.milestones = milestones
        self.runs = runs

    def current(self) -> SessionView | None:
        with self.db.session() as s:
            row = s.execute(select(ProcessingRun.id, ProcessingRun.milestone_id)
                            .join(Milestone, Milestone.id == ProcessingRun.milestone_id)
                            .order_by(ProcessingRun.id.desc()).limit(1)).first()
        if row is None:
            return None
        return SessionView(self.milestones.get_milestone(row.milestone_id), self.runs.get_run(row.id))

    def validate_scope(self, file_name: str, data: bytes) -> ScopeReport:
        return self.milestones.check_scope(file_name, data)

    def start(self, file_name: str, data: bytes) -> SessionView:
        """Validate the scope workbook; only if it is valid, replace the session with a new one built on it.
        A rejected file leaves the current session untouched."""
        report = self.milestones.check_scope(file_name, data)
        if not report.valid:
            raise ScopeRejectedError(report)
        self.reset()
        m = self.milestones.create_milestone(code_from_file_name(file_name), None, None)
        self.milestones.import_scope(m.id, file_name, data)
        self.milestones.lock_scope(m.id)
        run = self.runs.create_run(m.id, None)
        log.info("Session started from %s: %s tags", PurePath(file_name).name, run.scope_tag_count)
        return SessionView(self.milestones.get_milestone(m.id), run)

    def reset(self) -> None:
        """Discard the session: the database and every stored scope, source and generated file."""
        self.db.recreate()
        self.files.clear_milestones()
        log.info("Session reset")
