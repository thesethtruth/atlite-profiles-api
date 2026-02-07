from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

class ProfileType(str, Enum):
    wind = "wind"
    solar = "solar"
    both = "both"


class WindTurbineConfig(BaseModel):
    """User-provided wind turbine definition for generation."""

    name: str = Field(min_length=1)
    hub_height_m: float = Field(gt=0)
    wind_speeds: list[float] = Field(min_length=2)
    power_curve_mw: list[float] = Field(min_length=2)
    rated_power_mw: float | None = Field(default=None, gt=0)
    manufacturer: str | None = None
    source: str | None = None

    @model_validator(mode="after")
    def _validate_curve_lengths(self) -> "WindTurbineConfig":
        if len(self.wind_speeds) != len(self.power_curve_mw):
            raise ValueError("wind_speeds and power_curve_mw must have the same length.")
        return self

    def to_atlite_turbine(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "HUB_HEIGHT": self.hub_height_m,
            "V": self.wind_speeds,
            "POW": self.power_curve_mw,
        }
        if self.rated_power_mw is not None:
            payload["P"] = self.rated_power_mw
        if self.manufacturer is not None:
            payload["manufacturer"] = self.manufacturer
        if self.source is not None:
            payload["source"] = self.source
        return payload


class SolarTechnologyConfig(BaseModel):
    """User-provided solar technology definition for generation."""

    name: str = Field(min_length=1)
    panel_parameters: dict[str, Any] = Field(min_length=1)
    manufacturer: str | None = None
    source: str | None = None

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, object],
        *,
        default_name: str = "API_Custom_Solar",
    ) -> "SolarTechnologyConfig":
        name = payload.get("name")
        manufacturer = payload.get("manufacturer")
        source = payload.get("source")
        panel_parameters = payload.get("panel_parameters")

        if isinstance(panel_parameters, dict):
            return cls(
                name=str(name or default_name),
                manufacturer=str(manufacturer) if manufacturer is not None else None,
                source=str(source) if source is not None else None,
                panel_parameters=panel_parameters,
            )

        # Support raw atlite-style YAML/JSON payloads without the wrapper key.
        raw_parameters = {
            key: value
            for key, value in payload.items()
            if key not in {"name", "manufacturer", "source"}
        }
        return cls(
            name=str(name or default_name),
            manufacturer=str(manufacturer) if manufacturer is not None else None,
            source=str(source) if source is not None else None,
            panel_parameters=raw_parameters,
        )

    def to_atlite_panel(self) -> dict[str, object]:
        payload = dict(self.panel_parameters)
        payload.setdefault("name", self.name)
        if self.manufacturer is not None:
            payload.setdefault("manufacturer", self.manufacturer)
        if self.source is not None:
            payload.setdefault("source", self.source)
        return payload


class GenerateProfilesRequest(BaseModel):
    profile_type: ProfileType = ProfileType.both
    latitude: float = Field(default=51.4713, ge=-90, le=90)
    longitude: float = Field(default=5.4186, ge=-180, le=180)
    base_path: Path = Path("data")
    output_dir: Path = Path("output")
    cutouts: list[str] = Field(default_factory=lambda: ["europe-2024-era5.nc"], min_length=1)
    turbine_model: str = "NREL_ReferenceTurbine_2020ATB_4MW"
    turbine_config: WindTurbineConfig | None = None
    slopes: list[float] = Field(default_factory=lambda: [30.0], min_length=1)
    azimuths: list[float] = Field(default_factory=lambda: [180.0], min_length=1)
    panel_model: str = "CSi"
    solar_technology_config: SolarTechnologyConfig | None = None
    visualize: bool = False

    @model_validator(mode="after")
    def _validate_orientation_lengths(self) -> "GenerateProfilesRequest":
        if len(self.slopes) != len(self.azimuths):
            raise ValueError("slopes and azimuths must have the same length.")
        return self


class GenerateProfilesResponse(BaseModel):
    status: Literal["ok"]
    profile_type: ProfileType
    wind_profiles: int = Field(ge=0)
    solar_profiles: int = Field(ge=0)
    output_dir: str


class ListItemsResponse(BaseModel):
    items: list[str]


class TurbineCatalogResponse(BaseModel):
    atlite: list[str]
    custom_turbines: list[str]


class SolarCatalogResponse(BaseModel):
    atlite: list[str]
    custom_solar_technologies: list[str]


class TurbineCurvePoint(BaseModel):
    speed: float
    power_mw: float


class TurbineCurveSummary(BaseModel):
    point_count: int
    speed_min: float | None
    speed_max: float | None


class TurbineMetadata(BaseModel):
    name: str
    manufacturer: str
    source: str
    provider: str
    hub_height_m: float | None
    rated_power_mw: float | None
    definition_file: str


class TurbineInspectResponse(BaseModel):
    status: Literal["ok"]
    turbine: str
    metadata: TurbineMetadata
    curve: list[TurbineCurvePoint]
    curve_summary: TurbineCurveSummary


class SolarMetadata(BaseModel):
    name: str
    manufacturer: str
    source: str
    provider: str
    definition_file: str


class SolarInspectResponse(BaseModel):
    status: Literal["ok"]
    technology: str
    metadata: SolarMetadata
    parameters: dict[str, Any]
