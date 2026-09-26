"""FastAPI application factory.

Run locally:  .venv\\Scripts\\python -m uvicorn backend.main:create_app --factory --port 8300
(the Vite dev UI runs on port 3300 and proxies /api to 8300)
Data location: MTL_DATA_DIR environment variable, default <repo>/MTL_DATA.
"""

import logging

from fastapi import FastAPI

from backend.api.comparison import router as comparison_router
from backend.api.consolidation import router as consolidation_router
from backend.api.milestones import router as milestones_router
from backend.api.runs import router as runs_router
from backend.config import Settings
from backend.services.comparison import ComparisonService
from backend.services.consolidation import ConsolidationService
from backend.services.milestones import MilestoneService
from backend.services.runs import RunService
from backend.storage.database import Database
from backend.storage.files import FileStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    files = FileStore(settings.data_dir)
    files.ensure_root()
    _configure_logging(files)

    db = Database(files.database_path)
    db.init()

    app = FastAPI(title="CDC MTL Tool", version="0.4.0-phase1d")
    app.state.settings = settings
    app.state.db = db
    app.state.milestone_service = MilestoneService(db, files)
    app.state.run_service = RunService(db, files)
    app.state.consolidation_service = ConsolidationService(db, files)
    app.state.comparison_service = ComparisonService(db, files)
    app.include_router(milestones_router)
    app.include_router(runs_router)
    app.include_router(consolidation_router)
    app.include_router(comparison_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "data_dir": str(settings.data_dir)}

    return app


def _configure_logging(files: FileStore) -> None:
    logger = logging.getLogger("backend")
    log_file = files.logs_dir / "mtl.log"
    if not any(getattr(h, "baseFilename", None) == str(log_file) for h in logger.handlers):
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
