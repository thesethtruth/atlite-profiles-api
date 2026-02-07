from pydantic import BaseModel, Field, model_validator


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
