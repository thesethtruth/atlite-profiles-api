import warnings
from pathlib import Path

import yaml

TurbineCatalog = dict[str, list[str]]
TurbineInspectPayload = dict[str, object]


def _configure_downstream_warning_filters() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated as an API\..*",
        category=UserWarning,
    )


_configure_downstream_warning_filters()


def _list_custom_turbines() -> list[str]:
    custom_turbines_dir = Path("custom_turbines")
    if not custom_turbines_dir.exists():
        return []
    return sorted({path.stem for path in custom_turbines_dir.glob("*.yaml")})


def _fetch_atlite_turbines() -> list[str]:
    import atlite.resource

    return sorted(set(atlite.resource.windturbines.keys()))


def _fetch_atlite_turbine_paths() -> dict[str, Path]:
    import atlite.resource

    return {name: Path(path) for name, path in atlite.resource.windturbines.items()}


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _value_to_mw(value: float) -> float:
    # Turbine YAMLs can store power in kW (e.g. 5600) or MW (e.g. 5.6).
    if value > 100:
        return value / 1000.0
    return value


def _resolve_turbine_file(turbine_model: str) -> tuple[str, Path]:
    custom_file = Path("custom_turbines") / f"{turbine_model}.yaml"
    if custom_file.exists():
        return "custom", custom_file

    try:
        atlite_files = _fetch_atlite_turbine_paths()
    except Exception:
        atlite_files = {}
    atlite_file = atlite_files.get(turbine_model)
    if atlite_file is not None and atlite_file.exists():
        return "atlite", atlite_file

    raise ValueError(f"Turbine '{turbine_model}' was not found.")


def _display_definition_file(
    *, source_kind: str, source_file: Path, turbine_model: str
) -> str:
    if source_kind == "atlite":
        return f"atlite/resources/windturbine/{turbine_model}"
    try:
        return str(source_file.relative_to(Path.cwd()))
    except ValueError:
        return str(source_file)


def _to_curve_points(payload: dict[str, object]) -> list[dict[str, float]]:
    speeds = payload.get("V")
    powers = payload.get("POW")
    if not isinstance(speeds, list) or not isinstance(powers, list):
        return []

    points: list[dict[str, float]] = []
    for speed, power in zip(speeds, powers):
        speed_value = _to_float(speed)
        power_value = _to_float(power)
        if speed_value is None or power_value is None:
            continue
        points.append({"speed": speed_value, "power_mw": _value_to_mw(power_value)})

    return points


def _rated_power_mw(payload: dict[str, object]) -> float | None:
    p_value = _to_float(payload.get("P"))
    if p_value is not None:
        return _value_to_mw(p_value)

    curve_points = _to_curve_points(payload)
    if curve_points:
        return max(point["power_mw"] for point in curve_points)

    return None


def inspect_turbine(turbine_model: str) -> TurbineInspectPayload:
    source_kind, source_file = _resolve_turbine_file(turbine_model)
    with source_file.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Turbine '{turbine_model}' has an invalid definition file.")

    curve = _to_curve_points(payload)
    speeds = [point["speed"] for point in curve]

    return {
        "status": "ok",
        "turbine": turbine_model,
        "metadata": {
            "name": str(payload.get("name") or turbine_model),
            "manufacturer": str(payload.get("manufacturer") or "unknown"),
            "source": str(payload.get("source") or source_kind),
            "provider": source_kind,
            "hub_height_m": _to_float(payload.get("HUB_HEIGHT")),
            "rated_power_mw": _rated_power_mw(payload),
            "definition_file": _display_definition_file(
                source_kind=source_kind,
                source_file=source_file,
                turbine_model=turbine_model,
            ),
        },
        "curve": curve,
        "curve_summary": {
            "point_count": len(curve),
            "speed_min": min(speeds) if speeds else None,
            "speed_max": max(speeds) if speeds else None,
        },
    }


def get_turbine_catalog() -> TurbineCatalog:
    return {
        "atlite": _fetch_atlite_turbines(),
        "custom_turbines": _list_custom_turbines(),
    }


def get_available_turbines() -> list[str]:
    catalog = get_turbine_catalog()
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
    turbine_config: dict[str, object] | None = None,
    visualize: bool = False,
) -> dict:
    from core.profile_generator import (
        ProfileConfig,
        ProfileGenerator,
        SolarConfig,
        WindConfig,
    )
    from core.models import WindTurbineConfig

    profile_config = ProfileConfig(
        location={"lat": latitude, "lon": longitude},
        base_path=base_path,
        output_dir=output_dir,
        cutouts=[Path(cutout) for cutout in cutouts],
    )
    parsed_turbine_config = (
        WindTurbineConfig.model_validate(turbine_config)
        if turbine_config is not None
        else None
    )
    wind_config = WindConfig(
        turbine_model=turbine_model,
        turbine_config=parsed_turbine_config,
    )
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
