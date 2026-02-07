from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.models import (
    GenerateProfilesResponse,
    SolarTechnologyConfig,
    WindTurbineConfig,
)
from service.logging_utils import configure_logging
from service.runner import (
    get_available_solar_technologies,
    get_available_turbines,
    inspect_solar_technology,
    inspect_turbine,
    run_profiles,
)

configure_logging()

app = FastAPI(
    title="Renewables Profiles API",
    version="0.1.0",
    root_path="/api",
)


class GenerateRequest(BaseModel):
    profile_type: str = "both"
    latitude: float = 51.4713
    longitude: float = 5.4186
    base_path: Path = Path("data")
    output_dir: Path = Path("output")
    cutouts: list[str] = Field(default_factory=lambda: ["europe-2024-era5.nc"])
    turbine_model: str = "NREL_ReferenceTurbine_2020ATB_4MW"
    turbine_config: WindTurbineConfig | None = None
    slopes: list[float] = Field(default_factory=lambda: [30.0])
    azimuths: list[float] = Field(default_factory=lambda: [180.0])
    panel_model: str = "CSi"
    solar_technology_config: SolarTechnologyConfig | None = None
    visualize: bool = False

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "profile_type": "both",
                    "latitude": 52.0,
                    "longitude": 5.0,
                    "base_path": "data",
                    "output_dir": "output",
                    "cutouts": ["europe-2024-era5.nc"],
                    "turbine_model": "NREL_ReferenceTurbine_2020ATB_4MW",
                    "turbine_config": {
                        "name": "API_Custom",
                        "hub_height_m": 120.0,
                        "wind_speeds": [0, 5, 10, 15, 25],
                        "power_curve_mw": [0, 0.2, 1.8, 3.9, 4.0],
                        "manufacturer": "ACME",
                        "source": "api",
                    },
                    "slopes": [30.0],
                    "azimuths": [180.0],
                    "panel_model": "CSi",
                    "solar_technology_config": {
                        "model": "huld",
                        "name": "API_Solar",
                        "efficiency": 0.1,
                        "c_temp_amb": 1.0,
                        "c_temp_irrad": 0.035,
                        "r_tamb": 293.0,
                        "r_tmod": 298.0,
                        "r_irradiance": 1000.0,
                        "k_1": -0.017162,
                        "k_2": -0.040289,
                        "k_3": -0.004681,
                        "k_4": 0.000148,
                        "k_5": 0.000169,
                        "k_6": 0.000005,
                        "inverter_efficiency": 0.9,
                        "manufacturer": "ACME",
                        "source": "api",
                    },
                    "visualize": False,
                }
            ]
        }
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/turbines")
def list_turbines() -> dict[str, list[str]]:
    return {"items": get_available_turbines()}


@app.get("/turbines/{turbine_model}")
def turbine_inspect(turbine_model: str) -> dict[str, object]:
    try:
        return inspect_turbine(turbine_model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/solar-technologies")
def list_solar_technologies() -> dict[str, list[str]]:
    return {"items": get_available_solar_technologies()}


@app.get("/solar-technologies/{technology}")
def solar_technology_inspect(technology: str) -> dict[str, object]:
    try:
        return inspect_solar_technology(technology)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/generate",
    response_model=GenerateProfilesResponse,
    responses={
        200: {
            "description": "Profiles generated successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "profile_type": "both",
                        "wind_profiles": 1,
                        "solar_profiles": 1,
                        "output_dir": "output",
                    }
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
                "value": {
                    "profile_type": "both",
                    "latitude": 52.0,
                    "longitude": 5.0,
                    "base_path": "data",
                    "output_dir": "output",
                    "cutouts": ["europe-2024-era5.nc"],
                    "turbine_model": "NREL_ReferenceTurbine_2020ATB_4MW",
                    "turbine_config": {
                        "name": "API_Custom",
                        "hub_height_m": 120.0,
                        "wind_speeds": [0, 5, 10, 15, 25],
                        "power_curve_mw": [0, 0.2, 1.8, 3.9, 4.0],
                    },
                    "slopes": [30.0],
                    "azimuths": [180.0],
                    "panel_model": "CSi",
                    "solar_technology_config": {
                        "model": "huld",
                        "name": "API_Solar",
                        "efficiency": 0.1,
                        "c_temp_amb": 1.0,
                        "c_temp_irrad": 0.035,
                        "r_tamb": 293.0,
                        "r_tmod": 298.0,
                        "r_irradiance": 1000.0,
                        "k_1": -0.017162,
                        "k_2": -0.040289,
                        "k_3": -0.004681,
                        "k_4": 0.000148,
                        "k_5": 0.000169,
                        "k_6": 0.000005,
                        "inverter_efficiency": 0.9,
                    },
                    "visualize": False,
                },
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


def serve() -> None:
    import uvicorn

    uvicorn.run("service.api:app", host="0.0.0.0", port=8000, reload=False)
