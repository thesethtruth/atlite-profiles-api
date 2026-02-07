import sys
import types
from pathlib import Path

import service.runner as runner_module
from service.runner import get_available_turbines, get_turbine_catalog, run_profiles


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


def test_configure_downstream_warning_filters(monkeypatch):
    captured: dict[str, object] = {}

    def fake_filterwarnings(
        action, message="", category=Warning, module="", lineno=0, append=False
    ):
        captured["action"] = action
        captured["message"] = message
        captured["category"] = category
        captured["module"] = module
        captured["lineno"] = lineno
        captured["append"] = append

    monkeypatch.setattr(runner_module.warnings, "filterwarnings", fake_filterwarnings)

    runner_module._configure_downstream_warning_filters()

    assert captured["action"] == "ignore"
    assert "pkg_resources is deprecated as an API" in str(captured["message"])
    assert captured["category"] is UserWarning


def test_get_turbine_catalog_live_fetch_with_local_custom(tmp_path, monkeypatch):
    fake_atlite_resource = types.SimpleNamespace(windturbines={"B": "x", "A": "y"})
    fake_atlite_module = types.SimpleNamespace(resource=fake_atlite_resource)
    monkeypatch.setitem(sys.modules, "atlite", fake_atlite_module)
    monkeypatch.setitem(sys.modules, "atlite.resource", fake_atlite_resource)

    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "Z.yaml").write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    catalog = get_turbine_catalog()
    assert catalog == {"atlite": ["A", "B"], "custom_turbines": ["Z"]}


def test_get_turbine_catalog_handles_missing_custom_dir(monkeypatch, tmp_path):
    fake_atlite_resource = types.SimpleNamespace(windturbines={"A": "x"})
    fake_atlite_module = types.SimpleNamespace(resource=fake_atlite_resource)
    monkeypatch.setitem(sys.modules, "atlite", fake_atlite_module)
    monkeypatch.setitem(sys.modules, "atlite.resource", fake_atlite_resource)
    monkeypatch.chdir(tmp_path)

    catalog = get_turbine_catalog()
    assert catalog == {"atlite": ["A"], "custom_turbines": []}


def test_get_available_turbines_deduplicates(monkeypatch):
    monkeypatch.setattr(
        runner_module,
        "get_turbine_catalog",
        lambda: {"atlite": ["A", "B"], "custom_turbines": ["B", "Z"]},
    )

    assert get_available_turbines() == ["A", "B", "Z"]
