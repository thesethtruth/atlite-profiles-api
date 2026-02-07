import sys
import types
from pathlib import Path

import service.runner as runner_module
from service.runner import (
    get_available_turbines,
    get_turbine_catalog,
    inspect_turbine,
    run_profiles,
)


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


def test_run_profiles_accepts_turbine_config(monkeypatch):
    captured: dict[str, object] = {}

    class CaptureWindConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_profile_module = types.SimpleNamespace(
        ProfileConfig=DummyProfileConfig,
        WindConfig=CaptureWindConfig,
        SolarConfig=DummySolarConfig,
        ProfileGenerator=DummyGenerator,
    )
    monkeypatch.setitem(sys.modules, "core.profile_generator", fake_profile_module)

    run_profiles(
        profile_type="wind",
        latitude=52.0,
        longitude=5.0,
        base_path=Path("/tmp"),
        output_dir=Path("out"),
        cutouts=["europe-2024-era5.nc"],
        turbine_model="ignored-when-config-present",
        turbine_config={
            "name": "API_Custom",
            "hub_height_m": 120,
            "wind_speeds": [0, 10, 20],
            "power_curve_mw": [0, 2, 4],
        },
        slopes=[30.0],
        azimuths=[180.0],
        panel_model="CSi",
        visualize=False,
    )

    assert captured["turbine_model"] == "ignored-when-config-present"
    assert captured["turbine_config"].name == "API_Custom"


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


def test_inspect_turbine_custom_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "Demo.yaml").write_text(
        (
            "name: Demo\n"
            "manufacturer: ACME\n"
            "source: local\n"
            "HUB_HEIGHT: 120\n"
            "P: 5600\n"
            "V: [0, 10, 20]\n"
            "POW: [0, 3200, 5600]\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner_module, "_fetch_atlite_turbine_paths", lambda: {})

    result = inspect_turbine("Demo")

    assert result["status"] == "ok"
    assert result["metadata"]["provider"] == "custom"
    assert result["metadata"]["definition_file"] == "custom_turbines/Demo.yaml"
    assert result["metadata"]["rated_power_mw"] == 5.6
    assert result["curve"][1] == {"speed": 10.0, "power_mw": 3.2}
    assert result["curve_summary"]["point_count"] == 3
    assert result["curve_summary"]["speed_max"] == 20.0


def test_inspect_turbine_uses_atlite_when_not_custom(tmp_path, monkeypatch):
    atlite_file = tmp_path / "atlite_demo.yaml"
    atlite_file.write_text(
        "HUB_HEIGHT: 90\nV: [3, 4, 5]\nPOW: [0.1, 0.2, 0.3]\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        runner_module,
        "_fetch_atlite_turbine_paths",
        lambda: {"ATLiteDemo": atlite_file},
    )

    result = inspect_turbine("ATLiteDemo")

    assert result["metadata"]["provider"] == "atlite"
    assert result["metadata"]["name"] == "ATLiteDemo"
    assert (
        result["metadata"]["definition_file"]
        == "atlite/resources/windturbine/ATLiteDemo"
    )
    assert result["metadata"]["hub_height_m"] == 90.0
    assert result["curve_summary"]["point_count"] == 3


def test_inspect_turbine_not_found(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner_module, "_fetch_atlite_turbine_paths", lambda: {})

    try:
        inspect_turbine("missing")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected inspect_turbine to raise ValueError.")
