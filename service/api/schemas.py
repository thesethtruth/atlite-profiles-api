from pydantic import BaseModel, Field

from core.models import SolarTechnologyConfig, WindTurbineConfig

GENERATE_INLINE_EXAMPLE = {
    "profile_type": "both",
    "latitude": 52.0,
    "longitude": 5.0,
    "cutouts": ["nl-2012-era5.nc"],
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
}

GENERATE_RESPONSE_EXAMPLE = {
    "status": "ok",
    "profile_type": "both",
    "wind_profiles": 1,
    "solar_profiles": 1,
    "wind_profile_data": {
        "2024_NREL_ReferenceTurbine_2020ATB_4MW": {
            "index": ["2024-01-01T00:00:00"],
            "values": [0.42],
        }
    },
    "solar_profile_data": {
        "2024_slope30.0_azimuth180.0": {
            "index": ["2024-01-01T00:00:00"],
            "values": [0.28],
        }
    },
}


class GenerateRequest(BaseModel):
    profile_type: str = "both"
    latitude: float = 51.4713
    longitude: float = 5.4186
    cutouts: list[str] = Field(default_factory=lambda: ["nl-2012-era5.nc"])
    turbine_model: str = "NREL_ReferenceTurbine_2020ATB_4MW"
    turbine_config: WindTurbineConfig | None = None
    slopes: list[float] = Field(default_factory=lambda: [30.0])
    azimuths: list[float] = Field(default_factory=lambda: [180.0])
    panel_model: str = "CSi"
    solar_technology_config: SolarTechnologyConfig | None = None

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [GENERATE_INLINE_EXAMPLE],
        },
    }
