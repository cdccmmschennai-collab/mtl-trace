"""Local file storage layout (TRD §10).

MTL_DATA/
├── database/mtl.db
├── milestones/<milestone-code>/
│   ├── scope/        original scope workbooks, content-addressed <sha256>.<ext>, immutable
│   ├── sources/      (Phase 1B+) content-addressed source documents
│   ├── canonical/run-NNN/   (Phase 1C) canonical dataset snapshot per run
│   ├── outputs/run-NNN/     (Phase 1C) generated workbooks per run
│   ├── extracted/  comparison/  review/
└── logs/

Generated artifacts live in a per-run folder and are never overwritten.
"""

import hashlib
import os
from pathlib import Path, PurePath

MILESTONE_SUBDIRS = ("scope", "sources", "extracted", "canonical", "comparison", "review", "outputs")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FileStore:
    def __init__(self, root: Path):
        self.root = root

    @property
    def database_path(self) -> Path:
        return self.root / "database" / "mtl.db"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    def ensure_root(self) -> None:
        for sub in ("database", "milestones", "logs"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def milestone_dir(self, milestone_code: str) -> Path:
        return self.root / "milestones" / milestone_code

    def ensure_milestone_dirs(self, milestone_code: str) -> None:
        base = self.milestone_dir(milestone_code)
        for sub in MILESTONE_SUBDIRS:
            (base / sub).mkdir(parents=True, exist_ok=True)

    def store_immutable(self, milestone_code: str, area: str, data: bytes, extension: str) -> tuple[str, str]:
        """Write `data` content-addressed under the milestone area; return (relative path, sha256).

        An identical file already present is reused, never rewritten. The write goes through a temp
        file so a crash can never leave a truncated file under a valid hash name.
        """
        digest = sha256_bytes(data)
        target_dir = self.milestone_dir(milestone_code) / area
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{digest}{extension.lower()}"
        if target.exists():
            if sha256_bytes(target.read_bytes()) != digest:
                raise RuntimeError(f"Stored file {target} does not match its content hash.")
        else:
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, target)
        return target.relative_to(self.root).as_posix(), digest

    @staticmethod
    def run_folder(run_number: int) -> str:
        return f"run-{run_number:03d}"

    def store_generated(self, milestone_code: str, area: str, run_number: int, file_name: str,
                        data: bytes) -> tuple[str, str]:
        """Write a generated artifact to `<area>/run-NNN/<file_name>`; return (relative path, sha256).

        Never overwrites: an existing file is an earlier run's evidence, so the write is refused.
        """
        if PurePath(file_name).name != file_name:
            raise ValueError(f"Invalid artifact file name {file_name!r}")
        target_dir = self.milestone_dir(milestone_code) / area / self.run_folder(run_number)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / file_name
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        try:
            os.link(tmp, target)                    # atomic create-if-absent; fails if target exists
        except FileExistsError:
            raise FileExistsError(f"{target} already exists; generated outputs are never overwritten.") from None
        finally:
            tmp.unlink(missing_ok=True)
        return target.relative_to(self.root).as_posix(), sha256_bytes(data)

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"Path {relative_path!r} escapes the data directory")
        return path

    def read_verified(self, relative_path: str, sha256: str) -> bytes:
        """Read a stored file and prove it is still the evidence that was recorded."""
        data = self.resolve(relative_path).read_bytes()
        if sha256_bytes(data) != sha256:
            raise RuntimeError(f"Stored file {relative_path} no longer matches its recorded SHA-256.")
        return data
