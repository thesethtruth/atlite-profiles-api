from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any

import yaml

from core import technology as technology_core
from core.catalog import (
    fetch_atlite_solar_paths,
    fetch_atlite_solar_technologies,
    fetch_atlite_turbine_paths,
    fetch_atlite_turbines,
)
from core.models import (
    CutoutFetchConfig,
    CutoutFetchConfigEntry,
    GenerateProfilesRequest,
    GenerateProfilesResponse,
    SolarCatalogResponse,
    TurbineCatalogResponse,
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
    return fetch_atlite_turbines()


def _fetch_atlite_turbine_paths() -> dict[str, Path]:
    return fetch_atlite_turbine_paths()


def _fetch_atlite_solar_technologies() -> list[str]:
    return fetch_atlite_solar_technologies()


def _fetch_atlite_solar_paths() -> dict[str, Path]:
    return fetch_atlite_solar_paths()


def inspect_turbine(turbine_model: str) -> TurbineInspectPayload:
    return technology_core.inspect_turbine(
        turbine_model,
        atlite_paths_fetcher=_fetch_atlite_turbine_paths,
    )


def inspect_solar_technology(technology: str) -> SolarInspectPayload:
    return technology_core.inspect_solar_technology(
        technology,
        atlite_paths_fetcher=_fetch_atlite_solar_paths,
    )


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


def _apply_cdsapi_env_fallback() -> None:
    if not os.environ.get("CDSAPI_KEY"):
        fallback_key = os.environ.get("CDS_KEY")
        if fallback_key:
            os.environ["CDSAPI_KEY"] = fallback_key
    if not os.environ.get("CDSAPI_URL"):
        fallback_url = os.environ.get("CDS_URL")
        if fallback_url:
            os.environ["CDSAPI_URL"] = fallback_url


def _normalize_slice(value: object, *, axis: str) -> slice:
    if isinstance(value, slice):
        return value
    if isinstance(value, list) and len(value) == 2:
        return slice(value[0], value[1])
    raise ValueError(f"cutout.{axis} must be a [start, stop] list.")


def _is_remote_target(target: str) -> bool:
    if len(target) < 3:
        return False
    if target[1:3] == ":\\":
        return False
    return ":" in target


def _resolve_target_path(target: str, filename: str) -> str:
    return f"{target.rstrip('/')}/{filename}"


def _remote_target_parts(target: str) -> tuple[str, str]:
    host, remote_dir = target.split(":", 1)
    if len(host) == 0 or len(remote_dir) == 0:
        raise ValueError(f"Invalid remote target '{target}'.")
    return host, remote_dir


def _remote_file_exists(target: str, filename: str) -> bool:
    host, remote_dir = _remote_target_parts(target)
    remote_file = _resolve_target_path(remote_dir, filename)
    result = subprocess.run(
        ["ssh", host, f"test -f {shlex.quote(remote_file)}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _copy_to_remote_target(local_file: Path, target: str, filename: str) -> str:
    host, remote_dir = _remote_target_parts(target)
    subprocess.run(
        ["ssh", host, f"mkdir -p {shlex.quote(remote_dir)}"],
        check=True,
        capture_output=True,
        text=True,
    )
    remote_file = _resolve_target_path(remote_dir, filename)
    destination = f"{host}:{remote_file}"
    subprocess.run(
        ["scp", str(local_file), destination],
        check=True,
        capture_output=True,
        text=True,
    )
    return destination


def _build_cutout_kwargs(
    entry: CutoutFetchConfigEntry, *, cutout_file: Path
) -> dict[str, Any]:
    cutout_kwargs = dict(entry.cutout)
    cutout_kwargs["path"] = cutout_file
    cutout_kwargs["x"] = _normalize_slice(cutout_kwargs["x"], axis="x")
    cutout_kwargs["y"] = _normalize_slice(cutout_kwargs["y"], axis="y")
    return cutout_kwargs


def fetch_cutouts(*, config_file: Path, force_refresh: bool = False) -> dict[str, Any]:
    import atlite

    _apply_cdsapi_env_fallback()
    payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    config = CutoutFetchConfig.model_validate(payload)

    fetched: list[str] = []
    skipped: list[str] = []

    for entry in config.cutouts:
        filename = entry.filename
        target = entry.target
        is_remote = _is_remote_target(target)

        destination = _resolve_target_path(target, filename)
        exists = (
            _remote_file_exists(target, filename)
            if is_remote
            else (Path(target) / filename).exists()
        )
        if exists and not force_refresh:
            skipped.append(destination)
            continue

        if is_remote:
            with tempfile.TemporaryDirectory() as tmp_dir:
                local_file = Path(tmp_dir) / filename
                cutout_kwargs = _build_cutout_kwargs(entry, cutout_file=local_file)
                cutout = atlite.Cutout(**cutout_kwargs)
                cutout.prepare(**dict(entry.prepare))
                fetched.append(_copy_to_remote_target(local_file, target, filename))
            continue

        local_dir = Path(target)
        local_dir.mkdir(parents=True, exist_ok=True)
        local_file = local_dir / filename
        if force_refresh and local_file.exists():
            local_file.unlink()
        cutout_kwargs = _build_cutout_kwargs(entry, cutout_file=local_file)
        cutout = atlite.Cutout(**cutout_kwargs)
        cutout.prepare(**dict(entry.prepare))
        fetched.append(str(local_file))

    return {
        "status": "ok",
        "fetched": fetched,
        "skipped": skipped,
        "fetched_count": len(fetched),
        "skipped_count": len(skipped),
    }


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
