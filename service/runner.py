from __future__ import annotations

import warnings
from pathlib import Path

import yaml

from core.models import (
    GenerateProfilesRequest,
    GenerateProfilesResponse,
    SolarCatalogResponse,
    SolarInspectResponse,
    SolarTechnologyConfig,
    TurbineCatalogResponse,
    TurbineInspectResponse,
)

TurbineCatalog = dict[str, list[str]]
TurbineInspectPayload = dict[str, object]
SolarCatalog = dict[str, list[str]]
SolarInspectPayload = dict[str, object]


def _configure_downstream_warning_filters() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated as an API\..*",
        category=UserWarning,
    )


_configure_downstream_warning_filters()


def _list_local_yaml_names(directory: str) -> list[str]:
    root = Path(directory)
    if not root.exists():
        return []
    return sorted({path.stem for path in root.glob("*.yaml")})


def _fetch_atlite_turbines() -> list[str]:
    import atlite.resource

    return sorted(set(atlite.resource.windturbines.keys()))


def _fetch_atlite_turbine_paths() -> dict[str, Path]:
    import atlite.resource

    return {name: Path(path) for name, path in atlite.resource.windturbines.items()}


def _fetch_atlite_solar_technologies() -> list[str]:
    import atlite.resource

    return sorted(set(atlite.resource.solarpanels.keys()))


def _fetch_atlite_solar_paths() -> dict[str, Path]:
    import atlite.resource

    return {name: Path(path) for name, path in atlite.resource.solarpanels.items()}


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _value_to_mw(value: float) -> float:
    # Turbine YAMLs can store power in kW (e.g. 5600) or MW (e.g. 5.6).
    if value > 100:
        return value / 1000.0
    return value


def _infer_power_scale(payload: dict[str, object]) -> float:
    """
    Infer a single power unit scale for the full turbine payload.
    Returns 1.0 when values already look like MW, or 0.001 when values look like kW.
    """
    values: list[float] = []

    p_value = _to_float(payload.get("P"))
    if p_value is not None:
        values.append(abs(p_value))

    pow_values = payload.get("POW")
    if isinstance(pow_values, list):
        for item in pow_values:
            numeric = _to_float(item)
            if numeric is not None:
                values.append(abs(numeric))

    if not values:
        return 1.0

    # kW-style payloads have magnitudes in the hundreds/thousands.
    if max(values) > 100:
        return 0.001
    return 1.0


def _resolve_technology_file(
    technology: str,
    *,
    local_dir: str,
    atlite_paths_fetcher,
    not_found_label: str,
) -> tuple[str, Path]:
    local_file = Path(local_dir) / f"{technology}.yaml"
    if local_file.exists():
        return "custom", local_file

    try:
        atlite_files = atlite_paths_fetcher()
    except Exception:
        atlite_files = {}

    atlite_file = atlite_files.get(technology)
    if atlite_file is not None and atlite_file.exists():
        return "atlite", atlite_file

    raise ValueError(f"{not_found_label} '{technology}' was not found.")


def _display_definition_file(
    *,
    source_kind: str,
    source_file: Path,
    technology: str,
    atlite_resource_kind: str,
) -> str:
    if source_kind == "atlite":
        return f"atlite/resources/{atlite_resource_kind}/{technology}"
    try:
        return str(source_file.relative_to(Path.cwd()))
    except ValueError:
        return str(source_file)


def _to_curve_points(payload: dict[str, object]) -> list[dict[str, float]]:
    speeds = payload.get("V")
    powers = payload.get("POW")
    if not isinstance(speeds, list) or not isinstance(powers, list):
        return []

    power_scale = _infer_power_scale(payload)
    points: list[dict[str, float]] = []
    for speed, power in zip(speeds, powers):
        speed_value = _to_float(speed)
        power_value = _to_float(power)
        if speed_value is None or power_value is None:
            continue
        points.append({"speed": speed_value, "power_mw": power_value * power_scale})

    return points


def _rated_power_mw(payload: dict[str, object]) -> float | None:
    power_scale = _infer_power_scale(payload)
    p_value = _to_float(payload.get("P"))
    if p_value is not None:
        return p_value * power_scale

    curve_points = _to_curve_points(payload)
    if curve_points:
        return max(point["power_mw"] for point in curve_points)

    return None


def inspect_turbine(turbine_model: str) -> TurbineInspectPayload:
    source_kind, source_file = _resolve_technology_file(
        turbine_model,
        local_dir="config/wind",
        atlite_paths_fetcher=_fetch_atlite_turbine_paths,
        not_found_label="Turbine",
    )
    with source_file.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Turbine '{turbine_model}' has an invalid definition file.")

    curve = _to_curve_points(payload)
    speeds = [point["speed"] for point in curve]

    response = TurbineInspectResponse(
        status="ok",
        turbine=turbine_model,
        metadata={
            "name": str(payload.get("name") or turbine_model),
            "manufacturer": str(payload.get("manufacturer") or "unknown"),
            "source": str(payload.get("source") or source_kind),
            "provider": source_kind,
            "hub_height_m": _to_float(payload.get("HUB_HEIGHT")),
            "rated_power_mw": _rated_power_mw(payload),
            "definition_file": _display_definition_file(
                source_kind=source_kind,
                source_file=source_file,
                technology=turbine_model,
                atlite_resource_kind="windturbine",
            ),
        },
        curve=curve,
        curve_summary={
            "point_count": len(curve),
            "speed_min": min(speeds) if speeds else None,
            "speed_max": max(speeds) if speeds else None,
        },
    )
    return response.model_dump()


def inspect_solar_technology(technology: str) -> SolarInspectPayload:
    source_kind, source_file = _resolve_technology_file(
        technology,
        local_dir="config/solar",
        atlite_paths_fetcher=_fetch_atlite_solar_paths,
        not_found_label="Solar technology",
    )
    with source_file.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Solar technology '{technology}' has an invalid definition file."
        )

    config = SolarTechnologyConfig.from_payload(payload, default_name=technology)
    response = SolarInspectResponse(
        status="ok",
        technology=technology,
        metadata={
            "name": config.name,
            "manufacturer": config.manufacturer or "unknown",
            "source": config.source or source_kind,
            "provider": source_kind,
            "definition_file": _display_definition_file(
                source_kind=source_kind,
                source_file=source_file,
                technology=technology,
                atlite_resource_kind="solarpanel",
            ),
        },
        parameters=config.parameters(),
    )
    return response.model_dump()


def get_turbine_catalog() -> TurbineCatalog:
    return TurbineCatalogResponse(
        atlite=_fetch_atlite_turbines(),
        custom_turbines=_list_local_yaml_names("config/wind"),
    ).model_dump()


def get_solar_catalog() -> SolarCatalog:
    return SolarCatalogResponse(
        atlite=_fetch_atlite_solar_technologies(),
        custom_solar_technologies=_list_local_yaml_names("config/solar"),
    ).model_dump()


def get_available_turbines() -> list[str]:
    catalog = get_turbine_catalog()
    return sorted(set(catalog["atlite"] + catalog["custom_turbines"]))


def get_available_solar_technologies() -> list[str]:
    catalog = get_solar_catalog()
    return sorted(set(catalog["atlite"] + catalog["custom_solar_technologies"]))


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
    solar_technology_config: dict[str, object] | None = None,
    visualize: bool = False,
) -> dict:
    from core.profile_generator import (
        ProfileConfig,
        ProfileGenerator,
        SolarConfig,
        WindConfig,
    )

    request = GenerateProfilesRequest.model_validate(
        {
            "profile_type": profile_type,
            "latitude": latitude,
            "longitude": longitude,
            "base_path": base_path,
            "output_dir": output_dir,
            "cutouts": cutouts,
            "turbine_model": turbine_model,
            "turbine_config": turbine_config,
            "slopes": slopes,
            "azimuths": azimuths,
            "panel_model": panel_model,
            "solar_technology_config": solar_technology_config,
            "visualize": visualize,
        }
    )

    profile_config = ProfileConfig(
        location={"lat": request.latitude, "lon": request.longitude},
        base_path=request.base_path,
        output_dir=request.output_dir,
        cutouts=[Path(cutout) for cutout in request.cutouts],
    )
    wind_config = WindConfig(
        turbine_model=request.turbine_model,
        turbine_config=request.turbine_config,
    )
    solar_config = SolarConfig(
        slopes=request.slopes,
        azimuths=request.azimuths,
        panel_model=request.panel_model,
        panel_config=request.solar_technology_config,
        output_subdir="solar_profiles",
    )
    generator = ProfileGenerator(
        profile_config=profile_config,
        wind_config=wind_config,
        solar_config=solar_config,
    )

    wind_count = 0
    solar_count = 0

    if request.profile_type in {"wind", "both"}:
        wind_profiles = generator.generate_wind_profiles()
        wind_count = len(wind_profiles)
        if request.visualize:
            generator.visualize_wind_profiles()

    if request.profile_type in {"solar", "both"}:
        solar_profiles = generator.generate_solar_profiles()
        solar_count = len(solar_profiles)
        if request.visualize:
            generator.visualize_solar_profiles_monthly(color_key="azimuth")

    response = GenerateProfilesResponse(
        status="ok",
        profile_type=request.profile_type,
        wind_profiles=wind_count,
        solar_profiles=solar_count,
        output_dir=str(request.output_dir),
    )
    return response.model_dump()
