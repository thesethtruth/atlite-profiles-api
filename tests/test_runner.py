import sys
import types
from pathlib import Path

import pytest

import service.runner as runner_module
from service.runner import (
    fetch_cutouts,
    get_available_solar_technologies,
    get_available_turbines,
    get_solar_catalog,
    get_turbine_catalog,
    inspect_solar_technology,
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


def test_run_profiles_accepts_solar_technology_config(monkeypatch):
    captured: dict[str, object] = {}

    class CaptureSolarConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_profile_module = types.SimpleNamespace(
        ProfileConfig=DummyProfileConfig,
        WindConfig=DummyWindConfig,
        SolarConfig=CaptureSolarConfig,
        ProfileGenerator=DummyGenerator,
    )
    monkeypatch.setitem(sys.modules, "core.profile_generator", fake_profile_module)

    run_profiles(
        profile_type="solar",
        latitude=52.0,
        longitude=5.0,
        base_path=Path("/tmp"),
        output_dir=Path("out"),
        cutouts=["europe-2024-era5.nc"],
        turbine_model="ModelA",
        slopes=[30.0],
        azimuths=[180.0],
        panel_model="ignored-when-config-present",
        solar_technology_config={
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
        },
        visualize=False,
    )

    assert captured["panel_model"] == "ignored-when-config-present"
    assert captured["panel_config"].name == "API_Solar"
    assert captured["panel_config"].model == "huld"


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

    custom_dir = tmp_path / "config/wind"
    custom_dir.mkdir(parents=True)
    (custom_dir / "Z.yaml").write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    catalog = get_turbine_catalog()
    assert catalog == {"atlite": ["A", "B"], "custom_turbines": ["Z"]}


def test_get_solar_catalog_live_fetch_with_local_custom(tmp_path, monkeypatch):
    fake_atlite_resource = types.SimpleNamespace(solarpanels={"CdTe": "x", "CSi": "y"})
    fake_atlite_module = types.SimpleNamespace(resource=fake_atlite_resource)
    monkeypatch.setitem(sys.modules, "atlite", fake_atlite_module)
    monkeypatch.setitem(sys.modules, "atlite.resource", fake_atlite_resource)

    custom_dir = tmp_path / "config/solar"
    custom_dir.mkdir(parents=True)
    (custom_dir / "MyPanel.yaml").write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    catalog = get_solar_catalog()
    assert catalog == {
        "atlite": ["CSi", "CdTe"],
        "custom_solar_technologies": ["MyPanel"],
    }


def test_get_turbine_catalog_handles_missing_custom_dir(monkeypatch, tmp_path):
    fake_atlite_resource = types.SimpleNamespace(windturbines={"A": "x"})
    fake_atlite_module = types.SimpleNamespace(resource=fake_atlite_resource)
    monkeypatch.setitem(sys.modules, "atlite", fake_atlite_module)
    monkeypatch.setitem(sys.modules, "atlite.resource", fake_atlite_resource)
    monkeypatch.chdir(tmp_path)

    catalog = get_turbine_catalog()
    assert catalog == {"atlite": ["A"], "custom_turbines": []}


def test_get_available_solar_technologies_deduplicates(monkeypatch):
    monkeypatch.setattr(
        runner_module,
        "get_solar_catalog",
        lambda: {
            "atlite": ["CSi", "CdTe"],
            "custom_solar_technologies": ["CdTe", "MyPanel"],
        },
    )

    assert get_available_solar_technologies() == ["CSi", "CdTe", "MyPanel"]


def test_get_available_turbines_deduplicates(monkeypatch):
    monkeypatch.setattr(
        runner_module,
        "get_turbine_catalog",
        lambda: {"atlite": ["A", "B"], "custom_turbines": ["B", "Z"]},
    )

    assert get_available_turbines() == ["A", "B", "Z"]


def test_fetch_cutouts_prepares_local_file(tmp_path, monkeypatch):
    config_file = tmp_path / "cutouts.yaml"
    config_file.write_text(
        (
            "cutouts:\n"
            "  - filename: local.nc\n"
            "    target: data\n"
            "    cutout:\n"
            "      module: era5\n"
            "      x: [1.0, 2.0]\n"
            "      y: [3.0, 4.0]\n"
            "      time: '2024'\n"
            "    prepare:\n"
            "      features: [height, wind, influx, temperature]\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    calls: list[dict[str, object]] = []

    class DummyCutout:
        def __init__(self, **kwargs):
            calls.append({"kwargs": kwargs})
            self.path = Path(kwargs["path"])

        def prepare(self, **kwargs):
            calls[-1]["prepare"] = kwargs
            self.path.write_text("ok", encoding="utf-8")

    monkeypatch.setitem(
        sys.modules, "atlite", types.SimpleNamespace(Cutout=DummyCutout)
    )

    result = fetch_cutouts(config_file=config_file, force_refresh=False)

    assert result["fetched_count"] == 1
    assert result["skipped_count"] == 0
    assert (tmp_path / "data/local.nc").exists()
    assert calls[0]["kwargs"]["module"] == "era5"
    assert isinstance(calls[0]["kwargs"]["x"], slice)
    assert isinstance(calls[0]["kwargs"]["y"], slice)
    assert calls[0]["prepare"]["features"] == [
        "height",
        "wind",
        "influx",
        "temperature",
    ]


def test_fetch_cutouts_filters_by_name(tmp_path, monkeypatch):
    config_file = tmp_path / "cutouts.yaml"
    config_file.write_text(
        (
            "cutouts:\n"
            "  - name: first\n"
            "    filename: first.nc\n"
            "    target: data\n"
            "    cutout:\n"
            "      module: era5\n"
            "      x: [1.0, 2.0]\n"
            "      y: [3.0, 4.0]\n"
            "      time: '2024'\n"
            "    prepare: {}\n"
            "  - name: second\n"
            "    filename: second.nc\n"
            "    target: data\n"
            "    cutout:\n"
            "      module: era5\n"
            "      x: [1.0, 2.0]\n"
            "      y: [3.0, 4.0]\n"
            "      time: '2024'\n"
            "    prepare: {}\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    prepared_paths: list[str] = []

    class DummyCutout:
        def __init__(self, **kwargs):
            self.path = Path(kwargs["path"])

        def prepare(self, **kwargs):
            prepared_paths.append(str(self.path))
            self.path.write_text("ok", encoding="utf-8")

    monkeypatch.setitem(
        sys.modules, "atlite", types.SimpleNamespace(Cutout=DummyCutout)
    )

    result = fetch_cutouts(config_file=config_file, force_refresh=False, name="second")

    assert result["fetched_count"] == 1
    assert prepared_paths == ["data/second.nc"]


def test_fetch_cutouts_validation_report_for_existing_local_file(tmp_path, monkeypatch):
    config_file = tmp_path / "cutouts.yaml"
    config_file.write_text(
        (
            "cutouts:\n"
            "  - name: existing\n"
            "    filename: existing.nc\n"
            "    target: data\n"
            "    cutout:\n"
            "      module: era5\n"
            "      x: [1.0, 2.0]\n"
            "      y: [3.0, 4.0]\n"
            "      time: '2024'\n"
            "    prepare:\n"
            "      features: [wind]\n"
        ),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "existing.nc").write_text("old", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from core.models import CutoutDefinition, CutoutInspectResponse, CutoutPrepareConfig

    monkeypatch.setattr(
        runner_module,
        "inspect_cutout_metadata",
        lambda _path, *, name: CutoutInspectResponse(
            filename=name,
            path="data/existing.nc",
            cutout=CutoutDefinition(
                module="era5",
                x=[1.0, 2.0],
                y=[3.0, 4.0],
                time="2024",
            ),
            prepare=CutoutPrepareConfig(features=["wind"]),
            inferred=True,
        ),
    )

    result = fetch_cutouts(
        config_file=config_file,
        force_refresh=False,
        report_validate_existing=True,
    )

    report = result["validation_report"]
    assert report["checked"] == 1
    assert report["matched"] == 1
    assert report["mismatched"] == 0
    assert report["missing"] == 0
    assert report["entries"][0]["expected"] == {
        "module": "era5",
        "x": [1.0, 2.0],
        "y": [3.0, 4.0],
        "time": "2024",
        "features": ["wind"],
    }
    assert report["entries"][0]["observed"] == {
        "module": "era5",
        "x": [1.0, 2.0],
        "y": [3.0, 4.0],
        "time": "2024",
        "features": ["wind"],
    }


def test_fetch_cutouts_skips_existing_unless_force_refresh(tmp_path, monkeypatch):
    config_file = tmp_path / "cutouts.yaml"
    config_file.write_text(
        (
            "cutouts:\n"
            "  - filename: existing.nc\n"
            "    target: data\n"
            "    cutout:\n"
            "      module: era5\n"
            "      x: [1.0, 2.0]\n"
            "      y: [3.0, 4.0]\n"
            "      time: '2024'\n"
            "    prepare: {}\n"
        ),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    existing_file = data_dir / "existing.nc"
    existing_file.write_text("old", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    call_count = {"count": 0}

    class DummyCutout:
        def __init__(self, **kwargs):
            self.path = Path(kwargs["path"])

        def prepare(self, **kwargs):
            call_count["count"] += 1
            self.path.write_text("new", encoding="utf-8")

    monkeypatch.setitem(
        sys.modules, "atlite", types.SimpleNamespace(Cutout=DummyCutout)
    )

    skipped = fetch_cutouts(config_file=config_file, force_refresh=False)
    refreshed = fetch_cutouts(config_file=config_file, force_refresh=True)

    assert skipped["fetched_count"] == 0
    assert skipped["skipped_count"] == 1
    assert refreshed["fetched_count"] == 1
    assert refreshed["skipped_count"] == 0
    assert call_count["count"] == 1
    assert existing_file.read_text(encoding="utf-8") == "new"


def test_fetch_cutouts_remote_target_uses_scp(tmp_path, monkeypatch):
    config_file = tmp_path / "cutouts.yaml"
    config_file.write_text(
        (
            "cutouts:\n"
            "  - filename: remote.nc\n"
            "    target: user@example.org:/srv/cutouts\n"
            "    cutout:\n"
            "      module: era5\n"
            "      x: [1.0, 2.0]\n"
            "      y: [3.0, 4.0]\n"
            "      time: '2024'\n"
            "    prepare: {}\n"
        ),
        encoding="utf-8",
    )

    class DummyCutout:
        def __init__(self, **kwargs):
            self.path = Path(kwargs["path"])

        def prepare(self, **kwargs):
            self.path.write_text("remote", encoding="utf-8")

    commands: list[list[str]] = []

    class DummyCompleted:
        def __init__(self, returncode: int):
            self.returncode = returncode

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        if cmd[:2] == ["ssh", "user@example.org"] and "test -f" in cmd[2]:
            return DummyCompleted(returncode=1)
        return DummyCompleted(returncode=0)

    monkeypatch.setitem(
        sys.modules, "atlite", types.SimpleNamespace(Cutout=DummyCutout)
    )
    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    result = fetch_cutouts(config_file=config_file, force_refresh=False)

    assert result["fetched_count"] == 1
    assert result["skipped_count"] == 0
    assert any(cmd[0] == "scp" for cmd in commands)


def test_inspect_turbine_custom_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/wind"
    custom_dir.mkdir(parents=True)
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
    assert result["metadata"]["definition_file"] == "config/wind/Demo.yaml"
    assert result["metadata"]["rated_power_mw"] == pytest.approx(5.6)
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


def test_inspect_turbine_infers_power_unit_once_for_full_curve(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/wind"
    custom_dir.mkdir(parents=True)
    (custom_dir / "MixedUnits.yaml").write_text(
        ("HUB_HEIGHT: 100\nV: [0, 10, 20]\nPOW: [0, 50, 5600]\n"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner_module, "_fetch_atlite_turbine_paths", lambda: {})

    result = inspect_turbine("MixedUnits")

    # Inferred as kW for the full payload, so all POW values are scaled consistently.
    assert result["curve"][1] == {"speed": 10.0, "power_mw": 0.05}
    assert result["metadata"]["rated_power_mw"] == pytest.approx(5.6)


def test_inspect_solar_technology_custom_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/solar"
    custom_dir.mkdir(parents=True)
    (custom_dir / "DemoPanel.yaml").write_text(
        (
            "model: huld\n"
            "name: DemoPanel\n"
            "manufacturer: ACME\n"
            "source: local\n"
            "efficiency: 0.1\n"
            "c_temp_amb: 1\n"
            "c_temp_irrad: 0.035\n"
            "r_tamb: 293\n"
            "r_tmod: 298\n"
            "r_irradiance: 1000\n"
            "k_1: -0.017162\n"
            "k_2: -0.040289\n"
            "k_3: -0.004681\n"
            "k_4: 0.000148\n"
            "k_5: 0.000169\n"
            "k_6: 0.000005\n"
            "inverter_efficiency: 0.9\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner_module, "_fetch_atlite_solar_paths", lambda: {})

    result = inspect_solar_technology("DemoPanel")

    assert result["status"] == "ok"
    assert result["metadata"]["provider"] == "custom"
    assert result["metadata"]["definition_file"] == "config/solar/DemoPanel.yaml"
    assert result["parameters"]["model"] == "huld"
    assert result["parameters"]["efficiency"] == 0.1


def test_inspect_turbine_not_found(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner_module, "_fetch_atlite_turbine_paths", lambda: {})

    try:
        inspect_turbine("missing")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected inspect_turbine to raise ValueError.")
