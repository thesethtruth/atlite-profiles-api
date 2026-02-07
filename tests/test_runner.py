import sys
import types
from pathlib import Path

import service.runner as runner_module
from service.runner import (
    get_available_turbines,
    get_turbine_catalog,
    get_turbine_catalog_with_source,
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
    assert captured["module"] == r"atlite\.resource"


def test_get_turbine_catalog_from_cache_plus_local_custom(tmp_path, monkeypatch):
    cache_file = tmp_path / "turbines.json"
    cache_file.write_text(
        '{"generated_at": "2026-02-07T00:00:00Z", "atlite": ["A"]}',
        encoding="utf-8",
    )

    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "C1.yaml").write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert get_turbine_catalog(cache_path=cache_file) == {
        "atlite": ["A"],
        "custom_turbines": ["C1"],
    }


def test_get_available_turbines_backward_compatible_items_cache(tmp_path, monkeypatch):
    cache_file = tmp_path / "turbines.json"
    cache_file.write_text(
        '{"generated_at": "2026-02-07T00:00:00Z", "items": ["A", "B"]}',
        encoding="utf-8",
    )

    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "Z.yaml").write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert get_available_turbines(cache_path=cache_file) == ["A", "B", "Z"]


def test_get_turbine_catalog_force_update(monkeypatch, tmp_path):
    fake_atlite_resource = types.SimpleNamespace(windturbines={"B": "x", "A": "y"})
    fake_atlite_module = types.SimpleNamespace(resource=fake_atlite_resource)

    monkeypatch.setitem(sys.modules, "atlite", fake_atlite_module)
    monkeypatch.setitem(sys.modules, "atlite.resource", fake_atlite_resource)

    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "Z.yaml").write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    cache_file = tmp_path / ".cache" / "turbines.json"
    catalog = get_turbine_catalog(force_update=True, cache_path=cache_file)

    assert catalog == {"atlite": ["A", "B"], "custom_turbines": ["Z"]}
    assert cache_file.exists()


def test_get_turbine_catalog_cache_missing_returns_empty(tmp_path):
    missing = tmp_path / "missing.json"
    catalog = get_turbine_catalog(cache_path=missing)
    assert catalog["atlite"] == []
    assert isinstance(catalog["custom_turbines"], list)


def test_get_turbine_catalog_with_source_cache(tmp_path, monkeypatch):
    cache_file = tmp_path / "turbines.json"
    cache_file.write_text(
        '{"generated_at": "2026-02-07T00:00:00Z", "atlite": ["A"]}',
        encoding="utf-8",
    )
    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "LocalOnly.yaml").write_text("", encoding="utf-8")

    # Keep this test isolated from repository-level custom_turbines.
    monkeypatch.chdir(tmp_path)
    catalog, source = get_turbine_catalog_with_source(cache_path=cache_file)

    assert catalog["atlite"] == ["A"]
    assert catalog["custom_turbines"] == ["LocalOnly"]
    assert source == "cache"


def test_get_turbine_catalog_with_source_cache_miss_includes_local_custom(
    tmp_path, monkeypatch
):
    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "LocalOnly.yaml").write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    cache_file = tmp_path / "missing.json"
    catalog, source = get_turbine_catalog_with_source(cache_path=cache_file)
    assert catalog == {"atlite": [], "custom_turbines": ["LocalOnly"]}
    assert source == "cache-miss"
