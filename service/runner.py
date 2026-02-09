from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from core import technology as technology_core
from core.catalog import (
    fetch_atlite_solar_paths,
    fetch_atlite_solar_technologies,
    fetch_atlite_turbine_paths,
    fetch_atlite_turbines,
)
from core.cutout_metadata import inspect_cutout_metadata
from core.models import (
    CutoutFetchConfig,
    CutoutFetchConfigEntry,
    CutoutFetchResponse,
    CutoutValidationEntry,
    CutoutValidationReport,
    GenerateProfilesDataResponse,
    GenerateProfilesRequest,
    GenerateProfilesStoredResponse,
    ProfileSeriesPayload,
    SolarCatalogResponse,
    SolarInspectResponse,
    SolarTechnologyConfig,
    TurbineCatalogResponse,
    TurbineInspectResponse,
    WindTurbineConfig,
)
from core.storage import (
    AbstractFileHandler,
    LocalFileHandler,
    StorageConfig,
    store_profiles_as_csv_blobs,
)


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


def inspect_turbine(turbine_model: str) -> TurbineInspectResponse:
    payload = technology_core.inspect_turbine(
        turbine_model,
        atlite_paths_fetcher=_fetch_atlite_turbine_paths,
    )
    return TurbineInspectResponse.model_validate(payload)


def inspect_solar_technology(technology: str) -> SolarInspectResponse:
    payload = technology_core.inspect_solar_technology(
        technology,
        atlite_paths_fetcher=_fetch_atlite_solar_paths,
    )
    return SolarInspectResponse.model_validate(payload)


def get_turbine_catalog() -> TurbineCatalogResponse:
    return TurbineCatalogResponse(
        atlite=_fetch_atlite_turbines(),
        custom_turbines=_list_local_yaml_names("config/wind"),
    )


def get_solar_catalog() -> SolarCatalogResponse:
    return SolarCatalogResponse(
        atlite=_fetch_atlite_solar_technologies(),
        custom_solar_technologies=_list_local_yaml_names("config/solar"),
    )


def get_available_turbines() -> list[str]:
    catalog = get_turbine_catalog()
    return sorted(set(catalog.atlite + catalog.custom_turbines))


def get_available_solar_technologies() -> list[str]:
    catalog = get_solar_catalog()
    return sorted(set(catalog.atlite + catalog.custom_solar_technologies))


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


def _normalize_time(value: object) -> str:
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return str(value)


def _to_float_list(value: object) -> list[float]:
    if not isinstance(value, list):
        return []
    converted: list[float] = []
    for item in value:
        if not isinstance(item, (int, float)):
            return []
        converted.append(float(item))
    return converted


def _close_enough(a: float, b: float, *, tolerance: float = 1e-6) -> bool:
    return abs(a - b) <= tolerance


def _expected_cutout_metadata(entry: CutoutFetchConfigEntry) -> dict[str, Any]:
    return {
        "module": str(entry.cutout.get("module", "")),
        "x": _to_float_list(entry.cutout.get("x")),
        "y": _to_float_list(entry.cutout.get("y")),
        "time": _normalize_time(entry.cutout.get("time")),
        "features": sorted(
            str(item)
            for item in entry.prepare.get("features", [])  # type: ignore[arg-type]
        ),
    }


def _compare_cutout_to_config(
    entry: CutoutFetchConfigEntry, *, local_file: Path
) -> dict[str, Any]:
    observed = inspect_cutout_metadata(local_file, name=entry.filename)
    mismatches: list[str] = []
    expected = _expected_cutout_metadata(entry)
    found = {
        "module": observed.cutout.module,
        "x": observed.cutout.x,
        "y": observed.cutout.y,
        "time": _normalize_time(observed.cutout.time),
        "features": sorted(observed.prepare.features),
    }

    expected_module = expected["module"]
    if observed.cutout.module != expected_module:
        mismatches.append(
            f"module (expected={expected_module}, actual={observed.cutout.module})"
        )

    expected_x = expected["x"]
    if len(expected_x) == 2:
        if not (
            _close_enough(observed.cutout.x[0], expected_x[0])
            and _close_enough(observed.cutout.x[1], expected_x[1])
        ):
            mismatches.append(f"x (expected={expected_x}, actual={observed.cutout.x})")

    expected_y = expected["y"]
    if len(expected_y) == 2:
        if not (
            _close_enough(observed.cutout.y[0], expected_y[0])
            and _close_enough(observed.cutout.y[1], expected_y[1])
        ):
            mismatches.append(f"y (expected={expected_y}, actual={observed.cutout.y})")

    expected_time = expected["time"]
    actual_time = _normalize_time(observed.cutout.time)
    if expected_time != actual_time:
        mismatches.append(f"time (expected={expected_time}, actual={actual_time})")

    expected_features = expected["features"]
    actual_features = sorted(observed.prepare.features)
    if expected_features != actual_features:
        mismatches.append(
            f"features (expected={expected_features}, actual={actual_features})"
        )

    return {
        "name": entry.name,
        "filename": entry.filename,
        "path": str(local_file),
        "status": "match" if not mismatches else "mismatch",
        "mismatches": mismatches,
        "expected": expected,
        "observed": found,
    }


def _empty_validation_report() -> CutoutValidationReport:
    return CutoutValidationReport(
        enabled=True,
        checked=0,
        matched=0,
        mismatched=0,
        missing=0,
        remote_skipped=0,
        errors=0,
        entries=[],
    )


def fetch_cutouts(
    *,
    config_file: Path,
    force_refresh: bool = False,
    name: str | None = None,
    report_validate_existing: bool = False,
) -> CutoutFetchResponse:
    import atlite

    _apply_cdsapi_env_fallback()
    payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    config = CutoutFetchConfig.model_validate(payload)
    entries = list(config.cutouts)
    if name is not None:
        entries = [entry for entry in entries if entry.name == name]
        if not entries:
            raise ValueError(f"Cutout config name '{name}' was not found.")

    fetched: list[str] = []
    skipped: list[str] = []
    validation_report = _empty_validation_report() if report_validate_existing else None

    for entry in entries:
        filename = entry.filename
        target = entry.target
        is_remote = _is_remote_target(target)
        local_file = Path(target) / filename

        destination = _resolve_target_path(target, filename)
        exists = (
            _remote_file_exists(target, filename) if is_remote else local_file.exists()
        )

        if validation_report is not None:
            if is_remote:
                validation_report.remote_skipped += 1
                validation_report.entries.append(
                    CutoutValidationEntry(
                        name=entry.name,
                        filename=filename,
                        path=destination,
                        status="remote_skipped",
                        expected=_expected_cutout_metadata(entry),
                    )
                )
            elif exists:
                try:
                    result = _compare_cutout_to_config(entry, local_file=local_file)
                except Exception as exc:
                    validation_report.errors += 1
                    validation_report.entries.append(
                        CutoutValidationEntry(
                            name=entry.name,
                            filename=filename,
                            path=str(local_file),
                            status="error",
                            error=str(exc),
                            expected=_expected_cutout_metadata(entry),
                        )
                    )
                else:
                    validation_report.checked += 1
                    if result["status"] == "match":
                        validation_report.matched += 1
                    else:
                        validation_report.mismatched += 1
                    validation_report.entries.append(
                        CutoutValidationEntry.model_validate(result)
                    )
            else:
                validation_report.missing += 1
                validation_report.entries.append(
                    CutoutValidationEntry(
                        name=entry.name,
                        filename=filename,
                        path=str(local_file),
                        status="missing",
                        expected=_expected_cutout_metadata(entry),
                    )
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

    return CutoutFetchResponse(
        status="ok",
        fetched=fetched,
        skipped=skipped,
        fetched_count=len(fetched),
        skipped_count=len(skipped),
        validation_report=validation_report,
    )


def _serialize_profiles(
    profiles: dict[str, pd.Series],
) -> tuple[list[str], dict[str, ProfileSeriesPayload]]:
    if not profiles:
        return [], {}

    shared_index: list[str] | None = None
    serialized: dict[str, ProfileSeriesPayload] = {}
    for profile_key, profile in profiles.items():
        profile_index: list[str] = []
        for index in profile.index:
            if hasattr(index, "isoformat"):
                profile_index.append(index.isoformat())
            else:
                profile_index.append(str(index))

        if shared_index is None:
            shared_index = profile_index
        elif profile_index != shared_index:
            raise ValueError(
                "All generated profiles must share the same time index "
                "for API response serialization."
            )

        serialized[profile_key] = ProfileSeriesPayload(
            values=[float(value) for value in profile.to_list()],
        )

    return shared_index or [], serialized


def _build_generate_request(
    *,
    profile_type: str,
    latitude: float,
    longitude: float,
    base_path: Path,
    cutouts: list[str],
    turbine_model: str,
    slopes: list[float],
    azimuths: list[float],
    panel_model: str,
    turbine_config: WindTurbineConfig | None = None,
    solar_technology_config: SolarTechnologyConfig | None = None,
) -> GenerateProfilesRequest:
    return GenerateProfilesRequest.model_validate(
        {
            "profile_type": profile_type,
            "latitude": latitude,
            "longitude": longitude,
            "base_path": base_path,
            "cutouts": cutouts,
            "turbine_model": turbine_model,
            "turbine_config": turbine_config,
            "slopes": slopes,
            "azimuths": azimuths,
            "panel_model": panel_model,
            "solar_technology_config": solar_technology_config,
        }
    )


def _compute_profiles(
    request: GenerateProfilesRequest,
) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    from core.profile_generator import (
        ProfileConfig,
        ProfileGenerator,
        SolarConfig,
        WindConfig,
    )

    profile_config = ProfileConfig(
        location={"lat": request.latitude, "lon": request.longitude},
        base_path=request.base_path,
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
    )
    generator = ProfileGenerator(
        profile_config=profile_config,
        wind_config=wind_config,
        solar_config=solar_config,
    )

    wind_profiles: dict[str, pd.Series] = {}
    solar_profiles: dict[str, pd.Series] = {}

    if request.profile_type in {"wind", "both"}:
        wind_profiles = generator.generate_wind_profiles()

    if request.profile_type in {"solar", "both"}:
        solar_profiles = generator.generate_solar_profiles()
    return wind_profiles, solar_profiles


def generate_profiles(
    *,
    profile_type: str,
    latitude: float,
    longitude: float,
    base_path: Path,
    cutouts: list[str],
    turbine_model: str,
    slopes: list[float],
    azimuths: list[float],
    panel_model: str,
    turbine_config: WindTurbineConfig | None = None,
    solar_technology_config: SolarTechnologyConfig | None = None,
    include_profiles: bool = False,
) -> GenerateProfilesDataResponse:
    request = _build_generate_request(
        profile_type=profile_type,
        latitude=latitude,
        longitude=longitude,
        base_path=base_path,
        cutouts=cutouts,
        turbine_model=turbine_model,
        slopes=slopes,
        azimuths=azimuths,
        panel_model=panel_model,
        turbine_config=turbine_config,
        solar_technology_config=solar_technology_config,
    )
    wind_profiles, solar_profiles = _compute_profiles(request)
    index: list[str] | None = None
    wind_profile_data: dict[str, ProfileSeriesPayload] | None = None
    solar_profile_data: dict[str, ProfileSeriesPayload] | None = None
    if include_profiles:
        wind_index, wind_profile_data = _serialize_profiles(wind_profiles)
        solar_index, solar_profile_data = _serialize_profiles(solar_profiles)
        candidate_indices: list[list[str]] = []
        if wind_profile_data:
            candidate_indices.append(wind_index)
        if solar_profile_data:
            candidate_indices.append(solar_index)

        if candidate_indices:
            index = candidate_indices[0]
            for candidate in candidate_indices[1:]:
                if candidate != index:
                    raise ValueError(
                        "Wind and solar profiles must share the same time index "
                        "for API response serialization."
                    )
        else:
            index = []

    return GenerateProfilesDataResponse(
        status="ok",
        profile_type=request.profile_type,
        wind_profiles=len(wind_profiles),
        solar_profiles=len(solar_profiles),
        index=index,
        wind_profile_data=wind_profile_data,
        solar_profile_data=solar_profile_data,
    )


def generate_profiles_to_storage(
    *,
    profile_type: str,
    latitude: float,
    longitude: float,
    base_path: Path,
    cutouts: list[str],
    turbine_model: str,
    slopes: list[float],
    azimuths: list[float],
    panel_model: str,
    turbine_config: WindTurbineConfig | None = None,
    solar_technology_config: SolarTechnologyConfig | None = None,
    storage: StorageConfig,
    file_handler: AbstractFileHandler | None = None,
) -> GenerateProfilesStoredResponse:
    request = _build_generate_request(
        profile_type=profile_type,
        latitude=latitude,
        longitude=longitude,
        base_path=base_path,
        cutouts=cutouts,
        turbine_model=turbine_model,
        slopes=slopes,
        azimuths=azimuths,
        panel_model=panel_model,
        turbine_config=turbine_config,
        solar_technology_config=solar_technology_config,
    )
    wind_profiles, solar_profiles = _compute_profiles(request)
    active_file_handler = file_handler or LocalFileHandler(storage.output_dir)
    stored_files = store_profiles_as_csv_blobs(
        profiles=wind_profiles,
        output_subdir=storage.wind_output_subdir,
        file_handler=active_file_handler,
    )
    stored_files.extend(
        store_profiles_as_csv_blobs(
            profiles=solar_profiles,
            output_subdir=storage.solar_output_subdir,
            file_handler=active_file_handler,
        )
    )
    return GenerateProfilesStoredResponse(
        status="ok",
        profile_type=request.profile_type,
        wind_profiles=len(wind_profiles),
        solar_profiles=len(solar_profiles),
        output_dir=str(storage.output_dir),
        stored_files=stored_files,
    )
