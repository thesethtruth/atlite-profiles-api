import pytest

from core.models import CutoutFetchConfig, SolarTechnologyConfig, WindTurbineConfig


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
    assert payload["hub_height"] == 120
    assert payload["V"] == [0, 10, 20]
    assert payload["POW"] == [0, 2, 4]
    assert payload["P"] == 4
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


def test_solar_technology_config_huld_to_atlite_panel():
    config = SolarTechnologyConfig(
        model="huld",
        name="CSi",
        source="Huld 2010",
        efficiency=0.1,
        c_temp_amb=1.0,
        c_temp_irrad=0.035,
        r_tamb=293.0,
        r_tmod=298.0,
        r_irradiance=1000.0,
        k_1=-0.017162,
        k_2=-0.040289,
        k_3=-0.004681,
        k_4=0.000148,
        k_5=0.000169,
        k_6=0.000005,
        inverter_efficiency=0.9,
    )

    payload = config.to_atlite_panel()

    assert payload["model"] == "huld"
    assert payload["name"] == "CSi"
    assert payload["inverter_efficiency"] == 0.9


def test_solar_technology_config_unwraps_panel_parameters_wrapper():
    config = SolarTechnologyConfig.model_validate(
        {
            "name": "CdTe",
            "source": "Huld 2010",
            "panel_parameters": {
                "model": "huld",
                "efficiency": 0.1,
                "c_temp_amb": 1.0,
                "c_temp_irrad": 0.035,
                "r_tamb": 293.0,
                "r_tmod": 298.0,
                "r_irradiance": 1000.0,
                "k_1": -0.103251,
                "k_2": -0.040446,
                "k_3": -0.001667,
                "k_4": -0.002075,
                "k_5": -0.001445,
                "k_6": -0.000023,
                "inverter_efficiency": 0.9,
            },
        }
    )

    assert config.name == "CdTe"
    assert config.model == "huld"
    assert config.k_1 == -0.103251


def test_solar_technology_config_rejects_missing_model_specific_fields():
    with pytest.raises(ValueError, match="missing required field"):
        SolarTechnologyConfig(
            model="bofinger",
            name="Kaneka",
            inverter_efficiency=0.9,
        )


def test_cutout_fetch_config_validates_required_cutout_fields():
    config = CutoutFetchConfig.model_validate(
        {
            "cutouts": [
                {
                    "filename": "europe-2024-era5.nc",
                    "target": "data",
                    "cutout": {
                        "module": "era5",
                        "x": [2.5, 7.5],
                        "y": [50.5, 54.0],
                        "time": "2024",
                    },
                    "prepare": {
                        "features": ["height", "wind", "influx", "temperature"],
                    },
                }
            ]
        }
    )

    assert config.cutouts[0].filename == "europe-2024-era5.nc"
    assert config.cutouts[0].target == "data"


def test_cutout_fetch_config_rejects_missing_cutout_fields():
    with pytest.raises(ValueError, match="missing required field"):
        CutoutFetchConfig.model_validate(
            {
                "cutouts": [
                    {
                        "filename": "europe-2024-era5.nc",
                        "target": "data",
                        "cutout": {
                            "module": "era5",
                            "x": [2.5, 7.5],
                        },
                    }
                ]
            }
        )
