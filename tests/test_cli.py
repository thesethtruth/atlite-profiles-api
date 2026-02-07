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


def test_list_turbines_command(monkeypatch):
    monkeypatch.setattr(cli, "get_available_turbines", lambda: ["T1", "T2"])

    result = runner.invoke(cli.app, ["list-turbines"])

    assert result.exit_code == 0
    assert "T1" in result.stdout
    assert "T2" in result.stdout
