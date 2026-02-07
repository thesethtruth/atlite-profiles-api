import sys
import types
from pathlib import Path

from service.runner import get_available_turbines, run_profiles


class DummyGenerator:
    def __init__(self, profile_config, wind_config, solar_config):
        self.profile_config = profile_config
        self.wind_config = wind_config
        self.solar_config = solar_config

    def generate_wind_profiles(self):
        return {"2024_model": object()}

    def generate_solar_profiles(self):
        return {"2024_slope30_azimuth180": object(), "2024_slope15_azimuth90": object()}

    def visualize_wind_profiles(self):
        return None

    def visualize_solar_profiles_monthly(self, color_key="azimuth"):
        return None


class DummyProfileConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class DummyWindConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class DummySolarConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_run_profiles_counts(monkeypatch):
    fake_profile_module = types.SimpleNamespace(
        ProfileConfig=DummyProfileConfig,
        WindConfig=DummyWindConfig,
        SolarConfig=DummySolarConfig,
        ProfileGenerator=DummyGenerator,
    )
    monkeypatch.setitem(sys.modules, "core.profile_generator", fake_profile_module)

    result = run_profiles(
        profile_type="both",
        latitude=52.0,
        longitude=5.0,
        base_path=Path("/tmp"),
        output_dir=Path("out"),
        cutouts=["europe-2024-era5.nc"],
        turbine_model="ModelA",
        slopes=[30.0, 15.0],
        azimuths=[180.0, 90.0],
        panel_model="CSi",
        visualize=False,
    )

    assert result["status"] == "ok"
    assert result["wind_profiles"] == 1
    assert result["solar_profiles"] == 2
    assert result["output_dir"] == "out"


def test_get_available_turbines(monkeypatch):
    fake_cutout_module = types.SimpleNamespace(
        get_available_turbine_list=lambda: ["A", "B", "C"]
    )
    monkeypatch.setitem(sys.modules, "core.cutout_processing", fake_cutout_module)

    assert get_available_turbines() == ["A", "B", "C"]
