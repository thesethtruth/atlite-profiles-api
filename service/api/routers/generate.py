from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request

from core.models import GenerateProfilesResponse
from service.api.catalog import get_catalog_snapshot
from service.api.schemas import (
    GENERATE_INLINE_EXAMPLE,
    GENERATE_RESPONSE_EXAMPLE,
    GenerateRequest,
)
from service.runner import run_profiles

router = APIRouter(tags=["Generation"])


def _validate_cutout_coordinate_bounds(
    *,
    latitude: float,
    longitude: float,
    cutouts: list[str],
    catalog,
) -> None:
    out_of_bounds: list[str] = []
    for cutout in cutouts:
        metadata = catalog.cutout_metadata.get(cutout)
        if metadata is None:
            continue

        x_min, x_max = metadata.cutout.x
        y_min, y_max = metadata.cutout.y
        lon_in_bounds = x_min <= longitude <= x_max
        lat_in_bounds = y_min <= latitude <= y_max
        if not (lon_in_bounds and lat_in_bounds):
            out_of_bounds.append(
                (
                    f"{cutout} (x=[{x_min}, {x_max}], y=[{y_min}, {y_max}], "
                    f"requested=({latitude}, {longitude}))"
                )
            )

    if out_of_bounds:
        raise HTTPException(
            status_code=422,
            detail=(
                "Requested coordinates are outside cutout bounds for: "
                + "; ".join(out_of_bounds)
            ),
        )


def _resolve_cutout_paths(*, cutouts: list[str], catalog) -> list[str]:
    by_name = {entry.name: entry.path for entry in catalog.cutout_entries}
    return [by_name.get(cutout, cutout) for cutout in cutouts]


@router.post(
    "/generate",
    response_model=GenerateProfilesResponse,
    responses={
        200: {
            "description": "Profiles generated successfully.",
            "content": {
                "application/json": {
                    "example": GENERATE_RESPONSE_EXAMPLE,
                }
            },
        }
    },
)
def generate(
    request: Request,
    request_payload: GenerateRequest = Body(
        openapi_examples={
            "inline_custom_wind_and_solar": {
                "summary": "Generate with inline wind and solar configs",
                "value": GENERATE_INLINE_EXAMPLE,
            }
        }
    ),
) -> GenerateProfilesResponse:
    catalog = get_catalog_snapshot(request.app)
    if catalog.available_cutouts:
        unavailable = sorted(
            set(request_payload.cutouts) - set(catalog.available_cutouts)
        )
        if unavailable:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Unknown cutout(s): "
                    + ", ".join(unavailable)
                    + ". Check config/api.yaml cutout_sources."
                ),
            )
    _validate_cutout_coordinate_bounds(
        latitude=request_payload.latitude,
        longitude=request_payload.longitude,
        cutouts=request_payload.cutouts,
        catalog=catalog,
    )
    resolved_cutouts = _resolve_cutout_paths(
        cutouts=request_payload.cutouts,
        catalog=catalog,
    )

    response_payload = run_profiles(
        profile_type=request_payload.profile_type,
        latitude=request_payload.latitude,
        longitude=request_payload.longitude,
        base_path=Path("."),
        output_dir=request_payload.output_dir,
        cutouts=resolved_cutouts,
        turbine_model=request_payload.turbine_model,
        turbine_config=(
            request_payload.turbine_config.model_dump()
            if request_payload.turbine_config is not None
            else None
        ),
        slopes=request_payload.slopes,
        azimuths=request_payload.azimuths,
        panel_model=request_payload.panel_model,
        solar_technology_config=(
            request_payload.solar_technology_config.model_dump()
            if request_payload.solar_technology_config is not None
            else None
        ),
        visualize=request_payload.visualize,
    )
    return GenerateProfilesResponse.model_validate(response_payload)
