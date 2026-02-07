from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.models import WindTurbineConfig
from service.runner import get_available_turbines, inspect_turbine, run_profiles

app = FastAPI(title="Renewables Profiles API", version="0.1.0")


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
    visualize: bool = False


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


@app.post("/generate")
def generate(payload: GenerateRequest) -> dict:
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
        visualize=payload.visualize,
    )


def serve() -> None:
    import uvicorn

    uvicorn.run("service.api:app", host="0.0.0.0", port=8000, reload=False)
