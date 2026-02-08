from pathlib import Path

from pydantic import BaseModel, Field

from core.models import SolarTechnologyConfig, WindTurbineConfig

GENERATE_INLINE_EXAMPLE = {
    "profile_type": "both",
    "latitude": 52.0,
    "longitude": 5.0,
    "output_dir": "output",
    "cutouts": ["europe-2024-era5.nc"],
    "turbine_model": "NREL_ReferenceTurbine_2020ATB_4MW",
    "turbine_config": {
        "name": "API_Custom",
        "hub_height_m": 120.0,
        "wind_speeds": [0, 5, 10, 15, 25],
        "power_curve_mw": [0, 0.2, 1.8, 3.9, 4.0],
        "rated_power_mw": 4.0,
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

GENERATE_RESPONSE_EXAMPLE = {
    "status": "ok",
    "profile_type": "both",
    "wind_profiles": 1,
    "solar_profiles": 1,
    "output_dir": "output",
}


class GenerateRequest(BaseModel):
    profile_type: str = "both"
    latitude: float = 51.4713
    longitude: float = 5.4186
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
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [GENERATE_INLINE_EXAMPLE],
        },
    }
