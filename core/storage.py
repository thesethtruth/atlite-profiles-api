from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field


class StorageConfig(BaseModel):
    """Configuration for persisting generated profile files."""

    output_dir: Path
    wind_output_subdir: str = Field(default="wind_profiles", min_length=1)
    solar_output_subdir: str = Field(default="solar_profiles", min_length=1)


class AbstractFileHandler(ABC):
    """Storage interface for writing binary blobs."""

    @abstractmethod
    def write_blob(self, *, path: str, payload: bytes) -> str:
        """Persist a blob and return the destination identifier."""


class LocalFileHandler(AbstractFileHandler):
    """Local filesystem blob writer."""

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def write_blob(self, *, path: str, payload: bytes) -> str:
        destination = self.base_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return str(destination)


def store_profiles_as_csv_blobs(
    *,
    profiles: dict[str, pd.Series],
    output_subdir: str,
    file_handler: AbstractFileHandler,
) -> list[str]:
    """Serialize profile objects as CSV blobs through a storage backend."""
    stored_files: list[str] = []
    for profile_key, profile in profiles.items():
        relative_path = f"{output_subdir}/{profile_key}.csv"
        stored_files.append(
            file_handler.write_blob(
                path=relative_path,
                payload=profile.to_csv().encode("utf-8"),
            )
        )
    return stored_files
