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
            raise ValueError(
                "wind_speeds and power_curve_mw must have the same length."
            )
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

    model: Literal["huld", "bofinger"]
    name: str = Field(min_length=1)
    manufacturer: str | None = None
    source: str | None = None
    inverter_efficiency: float = Field(gt=0, le=1)

    # Huld model parameters
    efficiency: float | None = Field(default=None, gt=0)
    c_temp_amb: float | None = None
    c_temp_irrad: float | None = None
    r_tamb: float | None = None
    r_tmod: float | None = None
    r_irradiance: float | None = Field(default=None, gt=0)
    k_1: float | None = None
    k_2: float | None = None
    k_3: float | None = None
    k_4: float | None = None
    k_5: float | None = None
    k_6: float | None = None

    # Bofinger model parameters
    threshold: float | None = None
    area: float | None = Field(default=None, gt=0)
    rated_production: float | None = Field(default=None, gt=0)
    A: float | None = None
    B: float | None = None
    C: float | None = None
    D: float | None = None
    NOCT: float | None = None
    Tstd: float | None = None
    Tamb: float | None = None
    Intc: float | None = None
    ta: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _unwrap_or_infer_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        panel_parameters = value.get("panel_parameters")
        if isinstance(panel_parameters, dict):
            merged = dict(panel_parameters)
            for key in ("name", "manufacturer", "source", "model"):
                if key in value and value[key] is not None:
                    merged.setdefault(key, value[key])
            value = merged

        if "model" not in value:
            inferred = cls._infer_model(value)
            if inferred is not None:
                value = dict(value)
                value["model"] = inferred

        if "name" not in value or not value.get("name"):
            value = dict(value)
            value["name"] = "API_Custom_Solar"

        return value

    @staticmethod
    def _infer_model(payload: dict[str, Any]) -> str | None:
        huld_keys = {
            "efficiency",
            "c_temp_amb",
            "c_temp_irrad",
            "r_tamb",
            "r_tmod",
            "r_irradiance",
            "k_1",
            "k_2",
            "k_3",
            "k_4",
            "k_5",
            "k_6",
        }
        bofinger_keys = {
            "threshold",
            "area",
            "rated_production",
            "A",
            "B",
            "C",
            "D",
            "NOCT",
            "Tstd",
            "Tamb",
            "Intc",
            "ta",
        }
        payload_keys = set(payload.keys())
        if huld_keys.issubset(payload_keys):
            return "huld"
        if bofinger_keys.issubset(payload_keys):
            return "bofinger"
        return None

    @model_validator(mode="after")
    def _validate_model_specific_fields(self) -> "SolarTechnologyConfig":
        huld_required = [
            "efficiency",
            "c_temp_amb",
            "c_temp_irrad",
            "r_tamb",
            "r_tmod",
            "r_irradiance",
            "k_1",
            "k_2",
            "k_3",
            "k_4",
            "k_5",
            "k_6",
        ]
        bofinger_required = [
            "threshold",
            "area",
            "rated_production",
            "A",
            "B",
            "C",
            "D",
            "NOCT",
            "Tstd",
            "Tamb",
            "Intc",
            "ta",
        ]

        required_fields = huld_required if self.model == "huld" else bofinger_required
        missing = [field for field in required_fields if getattr(self, field) is None]
        if missing:
            raise ValueError(
                f"Solar model '{self.model}' is missing required field(s): "
                + ", ".join(missing)
            )
        return self

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, object],
        *,
        default_name: str = "API_Custom_Solar",
    ) -> "SolarTechnologyConfig":
        normalized: dict[str, object] = dict(payload)
        normalized.setdefault("name", default_name)
        return cls.model_validate(normalized)

    def parameters(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.model_dump(exclude_none=True).items()
            if key not in {"name", "manufacturer", "source"}
        }

    def to_atlite_panel(self) -> dict[str, object]:
        return self.model_dump(exclude_none=True)


class GenerateProfilesRequest(BaseModel):
    profile_type: ProfileType = ProfileType.both
    latitude: float = Field(default=51.4713, ge=-90, le=90)
    longitude: float = Field(default=5.4186, ge=-180, le=180)
    base_path: Path = Path("data")
    output_dir: Path = Path("output")
    cutouts: list[str] = Field(
        default_factory=lambda: ["europe-2024-era5.nc"], min_length=1
    )
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


class CutoutFetchConfigEntry(BaseModel):
    filename: str = Field(min_length=1)
    target: str = Field(min_length=1)
    cutout: dict[str, Any] = Field(default_factory=dict)
    prepare: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_cutout_payload(self) -> "CutoutFetchConfigEntry":
        required = {"module", "x", "y", "time"}
        missing = [key for key in required if key not in self.cutout]
        if missing:
            raise ValueError(
                "cutout payload is missing required field(s): " + ", ".join(missing)
            )
        return self


class CutoutFetchConfig(BaseModel):
    cutouts: list[CutoutFetchConfigEntry] = Field(min_length=1)


class ListItemsResponse(BaseModel):
    items: list[str]


class CutoutCatalogEntry(BaseModel):
    name: str
    path: str


class CutoutDefinition(BaseModel):
    module: str
    x: list[float]
    y: list[float]
    dx: float | None = None
    dy: float | None = None
    time: str | list[str]


class CutoutPrepareConfig(BaseModel):
    features: list[str] = Field(default_factory=list)


class CutoutInspectResponse(BaseModel):
    filename: str
    path: str
    cutout: CutoutDefinition
    prepare: CutoutPrepareConfig
    inferred: bool = True


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
