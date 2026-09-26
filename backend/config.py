import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Stamped on every processing run. Identifies the comparison rule set the run will be evaluated under
# (`rules/v1.yaml`, introduced with the comparison engine in Phase 1D).
RULES_VERSION = "v1"


@dataclass(frozen=True)
class Settings:
    data_dir: Path                   # the MTL_DATA root

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(data_dir=Path(os.environ.get("MTL_DATA_DIR", REPO_ROOT / "MTL_DATA")).resolve())
