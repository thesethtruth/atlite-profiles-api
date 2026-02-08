from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import yaml

from core.catalog import fetch_atlite_solar_paths, fetch_atlite_turbine_paths
from core.models import (
    SolarInspectResponse,
    SolarTechnologyConfig,
    TurbineInspectResponse,
)

TurbineInspectPayload = dict[str, object]
SolarInspectPayload = dict[str, object]


def to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def infer_power_scale(payload: dict[str, object]) -> float:
    """
    Infer a single power unit scale for the full turbine payload.
    Returns 1.0 when values already look like MW, or 0.001 when values look like kW.
    """
    values: list[float] = []

    p_value = to_float(payload.get("P"))
    if p_value is not None:
        values.append(abs(p_value))

    pow_values = payload.get("POW")
    if isinstance(pow_values, list):
        for item in pow_values:
            numeric = to_float(item)
            if numeric is not None:
                values.append(abs(numeric))

    if not values:
        return 1.0

    if max(values) > 100:
        return 0.001
    return 1.0


def to_curve_points(payload: dict[str, object]) -> list[dict[str, float]]:
    speeds = payload.get("V")
    powers = payload.get("POW")
    if not isinstance(speeds, list) or not isinstance(powers, list):
        return []

    power_scale = infer_power_scale(payload)
    points: list[dict[str, float]] = []
    for speed, power in zip(speeds, powers):
        speed_value = to_float(speed)
        power_value = to_float(power)
        if speed_value is None or power_value is None:
            continue
        points.append({"speed": speed_value, "power_mw": power_value * power_scale})

    return points


def rated_power_mw(payload: dict[str, object]) -> float | None:
    power_scale = infer_power_scale(payload)
    p_value = to_float(payload.get("P"))
    if p_value is not None:
        return p_value * power_scale

    curve_points = to_curve_points(payload)
    if curve_points:
        return max(point["power_mw"] for point in curve_points)

    return None


def turbine_metrics_from_file(path: Path | None) -> tuple[float | None, float | None]:
    if path is None or not path.exists():
        return None, None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        return None, None
    if not isinstance(payload, dict):
        return None, None

    rated_power = rated_power_mw(payload)
    if rated_power is None:
        pow_values = payload.get("POW")
        if isinstance(pow_values, list):
            float_values = [
                float(item) for item in pow_values if to_float(item) is not None
            ]
            if float_values:
                rated_power = max(float_values) * infer_power_scale(payload)

    return rated_power, to_float(payload.get("HUB_HEIGHT"))


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


def inspect_turbine(
    turbine_model: str,
    *,
    atlite_paths_fetcher: Callable[[], dict[str, Path]] = fetch_atlite_turbine_paths,
) -> TurbineInspectPayload:
    source_kind, source_file = _resolve_technology_file(
        turbine_model,
        local_dir="config/wind",
        atlite_paths_fetcher=atlite_paths_fetcher,
        not_found_label="Turbine",
    )
    with source_file.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Turbine '{turbine_model}' has an invalid definition file.")

    curve = to_curve_points(payload)
    speeds = [point["speed"] for point in curve]

    response = TurbineInspectResponse(
        status="ok",
        turbine=turbine_model,
        metadata={
            "name": str(payload.get("name") or turbine_model),
            "manufacturer": str(payload.get("manufacturer") or "unknown"),
            "source": str(payload.get("source") or source_kind),
            "provider": source_kind,
            "hub_height_m": to_float(payload.get("HUB_HEIGHT")),
            "rated_power_mw": rated_power_mw(payload),
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


def inspect_solar_technology(
    technology: str,
    *,
    atlite_paths_fetcher: Callable[[], dict[str, Path]] = fetch_atlite_solar_paths,
) -> SolarInspectPayload:
    source_kind, source_file = _resolve_technology_file(
        technology,
        local_dir="config/solar",
        atlite_paths_fetcher=atlite_paths_fetcher,
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
