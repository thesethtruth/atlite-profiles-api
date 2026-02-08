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
    assert payload["hub_height"] == 145
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
    assert payload["hub_height"] == 132
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
        (
            "name: MyPanel\n"
            "manufacturer: ACME\n"
            "panel_parameters:\n"
            "  model: huld\n"
            "  efficiency: 0.1\n"
            "  c_temp_amb: 1\n"
            "  c_temp_irrad: 0.035\n"
            "  r_tamb: 293\n"
            "  r_tmod: 298\n"
            "  r_irradiance: 1000\n"
            "  k_1: -0.017162\n"
            "  k_2: -0.040289\n"
            "  k_3: -0.004681\n"
            "  k_4: 0.000148\n"
            "  k_5: 0.000169\n"
            "  k_6: 0.000005\n"
            "  inverter_efficiency: 0.9\n"
        ),
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
    assert payload["model"] == "huld"
    assert payload["efficiency"] == 0.1
    assert payload["name"] == "MyPanel"


def test_solar_config_uses_custom_panel_raw_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "config/solar"
    custom_dir.mkdir(parents=True)
    (custom_dir / "RawPanel.yaml").write_text(
        (
            "model: bofinger\n"
            "name: RawPanel\n"
            "threshold: 1\n"
            "area: 1.22\n"
            "rated_production: 89.3\n"
            "A: 0.0659164166836276\n"
            "B: -4.44310393547042E-06\n"
            "C: 0.0122044905275824\n"
            "D: -0.0035\n"
            "NOCT: 318\n"
            "Tstd: 298\n"
            "Tamb: 293\n"
            "Intc: 800\n"
            "ta: 0.9\n"
            "inverter_efficiency: 0.9\n"
        ),
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
    assert payload["model"] == "bofinger"
    assert payload["A"] == 0.0659164166836276
    assert payload["name"] == "RawPanel"
