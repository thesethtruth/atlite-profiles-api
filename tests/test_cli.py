from typer.testing import CliRunner

from service import cli


runner = CliRunner()


def test_generate_command(monkeypatch):
    def fake_run_profiles(**kwargs):
        assert kwargs["profile_type"] == "wind"
        return {
            "wind_profiles": 1,
            "solar_profiles": 0,
            "output_dir": "output",
        }

    monkeypatch.setattr(cli, "run_profiles", fake_run_profiles)

    result = runner.invoke(cli.app, ["generate", "--profile-type", "wind"])

    assert result.exit_code == 0
    assert "Done: wind=1, solar=0, output=output" in result.stdout


def test_list_turbines_command_pretty_output(monkeypatch):
    monkeypatch.setattr(
        cli,
        "get_turbine_catalog_with_source",
        lambda force_update=False: (
            {"atlite": ["AT1"], "custom_turbines": ["CT1", "CT2"]},
            "cache",
        ),
    )

    result = runner.invoke(cli.app, ["list-turbines"])

    assert result.exit_code == 0
    assert "Available" in result.stdout
    assert "(atlite)" in result.stdout
    assert "(custom)" in result.stdout
    assert "Source (atlite):" in result.stdout
    assert "Source (custom):" in result.stdout
    assert "local" in result.stdout
    assert "AT1" in result.stdout
    assert "CT1" in result.stdout
    assert result.stdout.startswith("\n")
    assert "Source (atlite): cache\n\n" in result.stdout
    assert "\n\nSource (custom): local" in result.stdout


def test_list_turbines_force_update(monkeypatch):
    called = {"value": False}

    def fake_get_turbine_catalog(force_update=False):
        called["value"] = force_update
        return {"atlite": ["AT1"], "custom_turbines": []}, "refreshed"

    monkeypatch.setattr(
        cli, "get_turbine_catalog_with_source", fake_get_turbine_catalog
    )

    result = runner.invoke(cli.app, ["list-turbines", "--force-update"])

    assert result.exit_code == 0
    assert called["value"] is True
    assert "refreshed" in result.stdout
