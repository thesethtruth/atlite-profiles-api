from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from service.runner import get_available_solar_technologies, get_available_turbines


class CatalogSnapshot(BaseModel):
    available_turbines: list[str] = Field(default_factory=list)
    available_solar_technologies: list[str] = Field(default_factory=list)


def load_catalog_snapshot() -> CatalogSnapshot:
    try:
        turbines = get_available_turbines()
    except Exception:
        turbines = []

    try:
        solar_technologies = get_available_solar_technologies()
    except Exception:
        solar_technologies = []

    return CatalogSnapshot(
        available_turbines=turbines,
        available_solar_technologies=solar_technologies,
    )


def apply_catalog_snapshot(app: FastAPI, snapshot: CatalogSnapshot) -> None:
    app.state.catalog = snapshot

    # Backward compatibility for existing tests/consumers reading these attrs directly.
    app.state.available_turbines = list(snapshot.available_turbines)
    app.state.available_solar_technologies = list(snapshot.available_solar_technologies)


def get_catalog_snapshot(app: FastAPI) -> CatalogSnapshot:
    snapshot = getattr(app.state, "catalog", None)
    if isinstance(snapshot, CatalogSnapshot):
        return snapshot

    return CatalogSnapshot(
        available_turbines=list(getattr(app.state, "available_turbines", [])),
        available_solar_technologies=list(
            getattr(app.state, "available_solar_technologies", [])
        ),
    )
