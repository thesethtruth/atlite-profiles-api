from __future__ import annotations

from glob import glob
from pathlib import Path

import yaml
from fastapi import FastAPI
from pydantic import BaseModel, Field

from core.catalog import get_available_solar_technologies, get_available_turbines
from core.models import CutoutCatalogEntry, CutoutInspectResponse
from service.api.cutout_metadata import inspect_cutout_metadata


class CatalogSnapshot(BaseModel):
    available_turbines: list[str] = Field(default_factory=list)
    available_solar_technologies: list[str] = Field(default_factory=list)
    available_cutouts: list[str] = Field(default_factory=list)
    cutout_entries: list[CutoutCatalogEntry] = Field(default_factory=list)
    cutout_metadata: dict[str, CutoutInspectResponse] = Field(default_factory=dict)


class ApiConfig(BaseModel):
    cutout_sources: list[str] = Field(default_factory=list)


def _load_api_config(config_file: Path = Path("config/api.yaml")) -> ApiConfig:
    if not config_file.exists():
        return ApiConfig()
    payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    return ApiConfig.model_validate(payload or {})


def _discover_cutouts(sources: list[str]) -> tuple[list[str], list[CutoutCatalogEntry]]:
    discovered: dict[str, Path] = {}
    for source in sources:
        if any(token in source for token in "*?[]"):
            matches = [Path(path) for path in glob(source, recursive=True)]
        else:
            source_path = Path(source)
            if source_path.is_dir():
                matches = list(source_path.glob("*.nc"))
            elif source_path.suffix == ".nc" and source_path.exists():
                matches = [source_path]
            else:
                matches = []

        for match in matches:
            if match.is_file() and match.suffix == ".nc":
                current = discovered.get(match.name)
                resolved = match.resolve()
                if current is None or str(resolved) < str(current):
                    discovered[match.name] = resolved

    names = sorted(discovered)
    entries = [
        CutoutCatalogEntry(name=name, path=str(discovered[name])) for name in names
    ]
    return names, entries


def load_catalog_snapshot() -> CatalogSnapshot:
    config = _load_api_config()

    try:
        turbines = get_available_turbines()
    except Exception:
        turbines = []

    try:
        solar_technologies = get_available_solar_technologies()
    except Exception:
        solar_technologies = []

    available_cutouts, cutout_entries = _discover_cutouts(config.cutout_sources)
    cutout_metadata: dict[str, CutoutInspectResponse] = {}
    for entry in cutout_entries:
        try:
            cutout_metadata[entry.name] = inspect_cutout_metadata(
                Path(entry.path), name=entry.name
            )
        except Exception:
            # Keep startup resilient: metadata is best-effort and can be missing for
            # invalid or partially written files.
            continue

    return CatalogSnapshot(
        available_turbines=turbines,
        available_solar_technologies=solar_technologies,
        available_cutouts=available_cutouts,
        cutout_entries=cutout_entries,
        cutout_metadata=cutout_metadata,
    )


def apply_catalog_snapshot(app: FastAPI, snapshot: CatalogSnapshot) -> None:
    app.state.catalog = snapshot

    # Backward compatibility for existing tests/consumers reading these attrs directly.
    app.state.available_turbines = list(snapshot.available_turbines)
    app.state.available_solar_technologies = list(snapshot.available_solar_technologies)
    app.state.available_cutouts = list(snapshot.available_cutouts)
    app.state.cutout_entries = list(snapshot.cutout_entries)
    app.state.cutout_metadata = dict(snapshot.cutout_metadata)


def get_catalog_snapshot(app: FastAPI) -> CatalogSnapshot:
    snapshot = getattr(app.state, "catalog", None)
    if isinstance(snapshot, CatalogSnapshot):
        return snapshot

    return CatalogSnapshot(
        available_turbines=list(getattr(app.state, "available_turbines", [])),
        available_solar_technologies=list(
            getattr(app.state, "available_solar_technologies", [])
        ),
        available_cutouts=list(getattr(app.state, "available_cutouts", [])),
        cutout_entries=list(getattr(app.state, "cutout_entries", [])),
        cutout_metadata=dict(getattr(app.state, "cutout_metadata", {})),
    )
