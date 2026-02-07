import pytest

from core.profile_generator import SolarConfig, WindConfig


def test_wind_config_uses_custom_turbine_atlite_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/wind"
    custom_dir.mkdir(parents=True)
    (custom_dir / "MyCustom.yaml").write_text(
        ("HUB_HEIGHT: 145\nV: [0, 10, 20]\nPOW: [0, 2, 4]\n"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "core.profile_generator.get_available_turbine_list",
        lambda: ["MyCustom"],
    )

    config = WindConfig(turbine_model="MyCustom")
    payload = config.atlite_turbine()

    assert isinstance(payload, dict)
    assert payload["HUB_HEIGHT"] == 145
    assert payload["name"] == "MyCustom"


def test_wind_config_uses_custom_turbine_api_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/wind"
    custom_dir.mkdir(parents=True)
    (custom_dir / "MyApiStyle.yaml").write_text(
        (
            "name: MyApiStyle\n"
            "hub_height_m: 132\n"
            "wind_speeds: [0, 10, 20]\n"
            "power_curve_mw: [0, 2, 4]\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "core.profile_generator.get_available_turbine_list",
        lambda: ["MyApiStyle"],
    )

    config = WindConfig(turbine_model="MyApiStyle")
    payload = config.atlite_turbine()

    assert isinstance(payload, dict)
    assert payload["HUB_HEIGHT"] == 132
    assert payload["V"] == [0, 10, 20]
    assert payload["POW"] == [0, 2, 4]


def test_wind_config_rejects_invalid_custom_turbine_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/wind"
    custom_dir.mkdir(parents=True)
    (custom_dir / "Broken.yaml").write_text("foo: bar\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "core.profile_generator.get_available_turbine_list",
        lambda: ["Broken"],
    )

    config = WindConfig(turbine_model="Broken")

    with pytest.raises(ValueError, match="missing required turbine fields"):
        config.atlite_turbine()


def test_solar_config_uses_custom_panel_wrapper_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/solar"
    custom_dir.mkdir(parents=True)
    (custom_dir / "MyPanel.yaml").write_text(
        ("name: MyPanel\nmanufacturer: ACME\npanel_parameters:\n  A: 1.0\n  B: 2.0\n"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "core.profile_generator.get_available_solar_technology_list",
        lambda: ["MyPanel"],
    )

    config = SolarConfig(panel_model="MyPanel")
    payload = config.atlite_panel()

    assert isinstance(payload, dict)
    assert payload["A"] == 1.0
    assert payload["B"] == 2.0
    assert payload["name"] == "MyPanel"


def test_solar_config_uses_custom_panel_raw_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/solar"
    custom_dir.mkdir(parents=True)
    (custom_dir / "RawPanel.yaml").write_text(
        ("name: RawPanel\nA: 1.5\nB: 3.5\n"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "core.profile_generator.get_available_solar_technology_list",
        lambda: ["RawPanel"],
    )

    config = SolarConfig(panel_model="RawPanel")
    payload = config.atlite_panel()

    assert isinstance(payload, dict)
    assert payload["A"] == 1.5
    assert payload["B"] == 3.5
    assert payload["name"] == "RawPanel"
