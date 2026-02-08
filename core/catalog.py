from __future__ import annotations

import warnings
from pathlib import Path

from core.models import SolarCatalogResponse, TurbineCatalogResponse

TurbineCatalog = dict[str, list[str]]
SolarCatalog = dict[str, list[str]]


def configure_downstream_warning_filters() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated as an API\..*",
        category=UserWarning,
    )


def _list_local_yaml_names(directory: str | Path) -> list[str]:
    root = Path(directory)
    if not root.exists():
        return []
    return sorted({path.stem for path in root.glob("*.yaml")})


def fetch_atlite_turbines() -> list[str]:
    import atlite.resource

    return sorted(set(atlite.resource.windturbines.keys()))


def fetch_atlite_turbine_paths() -> dict[str, Path]:
    import atlite.resource

    return {name: Path(path) for name, path in atlite.resource.windturbines.items()}


def fetch_atlite_solar_technologies() -> list[str]:
    import atlite.resource

    return sorted(set(atlite.resource.solarpanels.keys()))


def fetch_atlite_solar_paths() -> dict[str, Path]:
    import atlite.resource

    return {name: Path(path) for name, path in atlite.resource.solarpanels.items()}


def get_turbine_catalog() -> TurbineCatalog:
    return TurbineCatalogResponse(
        atlite=fetch_atlite_turbines(),
        custom_turbines=_list_local_yaml_names("config/wind"),
    ).model_dump()


def get_solar_catalog() -> SolarCatalog:
    return SolarCatalogResponse(
        atlite=fetch_atlite_solar_technologies(),
        custom_solar_technologies=_list_local_yaml_names("config/solar"),
    ).model_dump()


def get_available_turbines() -> list[str]:
    catalog = get_turbine_catalog()
    return sorted(set(catalog["atlite"] + catalog["custom_turbines"]))


def get_available_solar_technologies() -> list[str]:
    catalog = get_solar_catalog()
    return sorted(set(catalog["atlite"] + catalog["custom_solar_technologies"]))
