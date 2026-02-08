from __future__ import annotations

from glob import glob
from pathlib import Path

import yaml
from fastapi import FastAPI
from pydantic import BaseModel, Field

from service.runner import get_available_solar_technologies, get_available_turbines


class CatalogSnapshot(BaseModel):
    available_turbines: list[str] = Field(default_factory=list)
    available_solar_technologies: list[str] = Field(default_factory=list)
    available_cutouts: list[str] = Field(default_factory=list)


class ApiConfig(BaseModel):
    cutout_sources: list[str] = Field(default_factory=list)


def _load_api_config(config_file: Path = Path("config/api.yaml")) -> ApiConfig:
    if not config_file.exists():
        return ApiConfig()
    payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    return ApiConfig.model_validate(payload or {})


def _discover_cutouts(sources: list[str]) -> list[str]:
    discovered: set[str] = set()
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
                discovered.add(match.name)

    return sorted(discovered)


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

    available_cutouts = _discover_cutouts(config.cutout_sources)

    return CatalogSnapshot(
        available_turbines=turbines,
        available_solar_technologies=solar_technologies,
        available_cutouts=available_cutouts,
    )


def apply_catalog_snapshot(app: FastAPI, snapshot: CatalogSnapshot) -> None:
    app.state.catalog = snapshot

    # Backward compatibility for existing tests/consumers reading these attrs directly.
    app.state.available_turbines = list(snapshot.available_turbines)
    app.state.available_solar_technologies = list(snapshot.available_solar_technologies)
    app.state.available_cutouts = list(snapshot.available_cutouts)


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
    )
