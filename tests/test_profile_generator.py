from pathlib import Path

import pytest

from core.profile_generator import WindConfig


def test_wind_config_uses_custom_turbine_atlite_yaml(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "MyCustom.yaml").write_text(
        (
            "HUB_HEIGHT: 145\n"
            "V: [0, 10, 20]\n"
            "POW: [0, 2, 4]\n"
        ),
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
    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
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
    custom_dir = tmp_path / "custom_turbines"
    custom_dir.mkdir()
    (custom_dir / "Broken.yaml").write_text("foo: bar\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "core.profile_generator.get_available_turbine_list",
        lambda: ["Broken"],
    )

    config = WindConfig(turbine_model="Broken")

    with pytest.raises(ValueError, match="missing required turbine fields"):
        config.atlite_turbine()
