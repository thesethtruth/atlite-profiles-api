from fastapi import APIRouter, Body

from core.models import GenerateProfilesResponse
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
    payload: GenerateRequest = Body(
        openapi_examples={
            "inline_custom_wind_and_solar": {
                "summary": "Generate with inline wind and solar configs",
                "value": GENERATE_INLINE_EXAMPLE,
            }
        }
    ),
) -> GenerateProfilesResponse:
    return run_profiles(
        profile_type=payload.profile_type,
        latitude=payload.latitude,
        longitude=payload.longitude,
        base_path=payload.base_path,
        output_dir=payload.output_dir,
        cutouts=payload.cutouts,
        turbine_model=payload.turbine_model,
        turbine_config=(
            payload.turbine_config.model_dump()
            if payload.turbine_config is not None
            else None
        ),
        slopes=payload.slopes,
        azimuths=payload.azimuths,
        panel_model=payload.panel_model,
        solar_technology_config=(
            payload.solar_technology_config.model_dump()
            if payload.solar_technology_config is not None
            else None
        ),
        visualize=payload.visualize,
    )
