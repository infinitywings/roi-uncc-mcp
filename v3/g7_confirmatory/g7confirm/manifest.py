"""Create-once artifact and provenance manifests."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class OutputExistsError(FileExistsError):
    """Raised when create-once output protection prevents an overwrite."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_once_json(path: str | Path, payload: Any) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise OutputExistsError(f"refusing to overwrite existing artifact: {output}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            output.unlink()
        except FileNotFoundError:
            pass
        raise
    return output


def build_manifest(*, root: str | Path, files: Iterable[str | Path],
                   metadata: dict[str, Any]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    entries = []
    for file in sorted((Path(item).resolve() for item in files), key=str):
        try:
            relative = file.relative_to(root_path)
        except ValueError as exc:
            raise ValueError(f"manifest input is outside root: {file}") from exc
        entries.append({"path": relative.as_posix(), "sha256": sha256_file(file),
                        "bytes": file.stat().st_size})
    return {
        "schema_version": "grideval-create-once-manifest/v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": root_path.as_posix(),
        "metadata": metadata,
        "files": entries,
    }

