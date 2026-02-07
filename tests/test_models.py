import pytest

from core.models import WindTurbineConfig


def test_wind_turbine_config_to_atlite_turbine():
    config = WindTurbineConfig(
        name="API_Custom",
        hub_height_m=120,
        wind_speeds=[0, 10, 20],
        power_curve_mw=[0, 2, 4],
        manufacturer="ACME",
        source="api",
    )

    payload = config.to_atlite_turbine()

    assert payload["name"] == "API_Custom"
    assert payload["HUB_HEIGHT"] == 120
    assert payload["V"] == [0, 10, 20]
    assert payload["POW"] == [0, 2, 4]
    assert payload["manufacturer"] == "ACME"
    assert payload["source"] == "api"


def test_wind_turbine_config_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        WindTurbineConfig(
            name="Broken",
            hub_height_m=120,
            wind_speeds=[0, 10, 20],
            power_curve_mw=[0, 2],
        )
