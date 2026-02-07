import json
import warnings
from datetime import UTC, datetime
from pathlib import Path

CACHE_PATH = Path(".cache/turbines.json")
TurbineCatalog = dict[str, list[str]]


def _configure_downstream_warning_filters() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated as an API\..*",
        category=UserWarning,
        module=r"atlite\.resource",
    )


_configure_downstream_warning_filters()


def _read_cached_catalog(cache_path: Path) -> TurbineCatalog | None:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    atlite_items = payload.get("atlite")
    if isinstance(atlite_items, list) and all(
        isinstance(item, str) for item in atlite_items
    ):
        return {"atlite": atlite_items, "custom_turbines": []}

    custom_items = payload.get("custom_turbines")
    if (
        isinstance(atlite_items, list)
        and isinstance(custom_items, list)
        and all(isinstance(item, str) for item in atlite_items)
        and all(isinstance(item, str) for item in custom_items)
    ):
        return {"atlite": atlite_items, "custom_turbines": custom_items}

    # Backward compatibility with old cache schema
    items = payload.get("items")
    if isinstance(items, list) and all(isinstance(item, str) for item in items):
        return {"atlite": items, "custom_turbines": []}
    return None


def _write_cached_catalog(cache_path: Path, catalog: TurbineCatalog) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "atlite": catalog["atlite"],
    }
    cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _list_custom_turbines() -> list[str]:
    custom_turbines_dir = Path("custom_turbines")
    if not custom_turbines_dir.exists():
        return []
    return sorted({path.stem for path in custom_turbines_dir.glob("*.yaml")})


def _fetch_atlite_turbines() -> list[str]:
    import atlite.resource

    return sorted(set(atlite.resource.windturbines.keys()))


def get_turbine_catalog(
    *, force_update: bool = False, cache_path: Path = CACHE_PATH
) -> TurbineCatalog:
    cached_catalog = _read_cached_catalog(cache_path)
    custom_turbines = _list_custom_turbines()
    if not force_update:
        atlite_turbines = (cached_catalog or {"atlite": []})["atlite"]
        return {"atlite": atlite_turbines, "custom_turbines": custom_turbines}

    if cache_path.exists():
        cache_path.unlink()
    catalog = {
        "atlite": _fetch_atlite_turbines(),
        "custom_turbines": custom_turbines,
    }
    _write_cached_catalog(cache_path, catalog)
    return catalog


def get_turbine_catalog_with_source(
    *, force_update: bool = False, cache_path: Path = CACHE_PATH
) -> tuple[TurbineCatalog, str]:
    if force_update:
        return get_turbine_catalog(
            force_update=True, cache_path=cache_path
        ), "refreshed"

    cached = _read_cached_catalog(cache_path)
    custom_turbines = _list_custom_turbines()
    if cached is None:
        return {"atlite": [], "custom_turbines": custom_turbines}, "cache-miss"
    return {"atlite": cached["atlite"], "custom_turbines": custom_turbines}, "cache"


def get_available_turbines(
    *, force_update: bool = False, cache_path: Path = CACHE_PATH
) -> list[str]:
    catalog = get_turbine_catalog(force_update=force_update, cache_path=cache_path)
    return sorted(set(catalog["atlite"] + catalog["custom_turbines"]))


def run_profiles(
    *,
    profile_type: str,
    latitude: float,
    longitude: float,
    base_path: Path,
    output_dir: Path,
    cutouts: list[str],
    turbine_model: str,
    slopes: list[float],
    azimuths: list[float],
    panel_model: str,
    visualize: bool = False,
) -> dict:
    from core.profile_generator import (
        ProfileConfig,
        ProfileGenerator,
        SolarConfig,
        WindConfig,
    )

    profile_config = ProfileConfig(
        location={"lat": latitude, "lon": longitude},
        base_path=base_path,
        output_dir=output_dir,
        cutouts=[Path(cutout) for cutout in cutouts],
    )
    wind_config = WindConfig(turbine_model=turbine_model)
    solar_config = SolarConfig(
        slopes=slopes,
        azimuths=azimuths,
        panel_model=panel_model,
        output_subdir="solar_profiles",
    )
    generator = ProfileGenerator(
        profile_config=profile_config,
        wind_config=wind_config,
        solar_config=solar_config,
    )

    wind_count = 0
    solar_count = 0

    if profile_type in {"wind", "both"}:
        wind_profiles = generator.generate_wind_profiles()
        wind_count = len(wind_profiles)
        if visualize:
            generator.visualize_wind_profiles()

    if profile_type in {"solar", "both"}:
        solar_profiles = generator.generate_solar_profiles()
        solar_count = len(solar_profiles)
        if visualize:
            generator.visualize_solar_profiles_monthly(color_key="azimuth")

    return {
        "status": "ok",
        "profile_type": profile_type,
        "wind_profiles": wind_count,
        "solar_profiles": solar_count,
        "output_dir": str(output_dir),
    }
