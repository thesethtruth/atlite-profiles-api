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

    response_payload = run_profiles(
        profile_type=request_payload.profile_type,
        latitude=request_payload.latitude,
        longitude=request_payload.longitude,
        base_path=request_payload.base_path,
        output_dir=request_payload.output_dir,
        cutouts=request_payload.cutouts,
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
