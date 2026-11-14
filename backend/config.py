import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Read-only resources (rules, built UI). In the packaged executable they are unpacked next to the code
# (PyInstaller's `sys._MEIPASS`); in a source checkout they live in the repository.
FROZEN = getattr(sys, "frozen", False)
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", REPO_ROOT)) if FROZEN else REPO_ROOT
RULES_DIR = RESOURCE_ROOT / "rules"
FRONTEND_DIST = RESOURCE_ROOT / "frontend" / "dist"

# Stamped on every processing run. Identifies the comparison rule set the run will be evaluated under
# (`rules/v1.yaml`, introduced with the comparison engine in Phase 1D).
RULES_VERSION = "v1"


def default_data_dir() -> Path:
    """Where working data lives: the repository's MTL_DATA in a checkout; the user's local app-data folder for
    the packaged tool (the executable's own folder may be read-only, and its unpack folder is temporary)."""
    if FROZEN:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "CDC MTL Tool" / "MTL_DATA"
    return REPO_ROOT / "MTL_DATA"


@dataclass(frozen=True)
class Settings:
    data_dir: Path                   # the MTL_DATA root
    fresh_start: bool = False        # discard any previous session when the app starts (the desktop tool)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(data_dir=Path(os.environ.get("MTL_DATA_DIR", default_data_dir())).resolve(),
                   fresh_start=os.environ.get("MTL_FRESH_START", "") == "1")
