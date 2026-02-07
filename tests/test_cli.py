from typer.testing import CliRunner
import re

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


def test_generate_command_reads_config_files(tmp_path, monkeypatch):
    turbine_file = tmp_path / "turbine.yaml"
    turbine_file.write_text(
        (
            "name: CLI_Custom\n"
            "hub_height_m: 120\n"
            "wind_speeds: [0, 10, 20]\n"
            "power_curve_mw: [0, 2, 4]\n"
        ),
        encoding="utf-8",
    )
    solar_file = tmp_path / "solar.yaml"
    solar_file.write_text(
        ("name: CLI_Solar\npanel_parameters:\n  A: 1.0\n  B: 2.0\n"),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_run_profiles(**kwargs):
        captured.update(kwargs)
        return {
            "wind_profiles": 1,
            "solar_profiles": 1,
            "output_dir": "output",
        }

    monkeypatch.setattr(cli, "run_profiles", fake_run_profiles)

    result = runner.invoke(
        cli.app,
        [
            "generate",
            "--turbine-config-file",
            str(turbine_file),
            "--solar-technology-config-file",
            str(solar_file),
        ],
    )

    assert result.exit_code == 0
    assert captured["turbine_config"]["name"] == "CLI_Custom"
    assert captured["solar_technology_config"]["name"] == "CLI_Solar"


def test_list_turbines_command_pretty_output(monkeypatch):
    monkeypatch.setattr(
        cli,
        "get_turbine_catalog",
        lambda: {"atlite": ["AT1"], "custom_turbines": ["CT1", "CT2"]},
    )

    result = runner.invoke(cli.app, ["list-turbines"])

    assert result.exit_code == 0
    assert "Available" in result.stdout
    assert "(atlite)" in result.stdout
    assert "(custom)" in result.stdout
    assert "Rated power (MW)" in result.stdout
    assert "Hub height (m)" in result.stdout
    assert "Source (atlite):" in result.stdout
    assert "Source (custom):" in result.stdout
    assert "local" in result.stdout
    assert "AT1" in result.stdout
    assert "CT1" in result.stdout
    assert result.stdout.startswith("\n")
    assert "Source (atlite): live\n\n" in result.stdout
    assert "\n\nSource (custom): local" in result.stdout


def test_list_turbines_command_no_turbines(monkeypatch):
    monkeypatch.setattr(
        cli,
        "get_turbine_catalog",
        lambda: {"atlite": [], "custom_turbines": []},
    )
    result = runner.invoke(cli.app, ["list-turbines"])
    assert result.exit_code == 0
    assert "No turbines found." in result.output


def test_turbine_metrics_from_file_prefers_p_in_kw(tmp_path):
    fp = tmp_path / "with_p.yaml"
    fp.write_text("P: 5600\nHUB_HEIGHT: 120\nPOW: [0, 1000, 5600]\n", encoding="utf-8")

    rated_power_mw, hub_height_m = cli._turbine_metrics_from_file(fp)

    assert rated_power_mw == "5.6"
    assert hub_height_m == "120"


def test_turbine_metrics_from_file_falls_back_to_max_pow(tmp_path):
    fp = tmp_path / "with_pow.yaml"
    fp.write_text("HUB_HEIGHT: 15\nPOW: [0, 0.0641, 0.072]\n", encoding="utf-8")

    rated_power_mw, hub_height_m = cli._turbine_metrics_from_file(fp)

    assert rated_power_mw == "0.072"
    assert hub_height_m == "15"


def test_turbine_metrics_from_file_uses_single_unit_scale(tmp_path):
    fp = tmp_path / "mixed_units.yaml"
    fp.write_text("HUB_HEIGHT: 120\nPOW: [0, 50, 5600]\n", encoding="utf-8")

    rated_power_mw, hub_height_m = cli._turbine_metrics_from_file(fp)

    assert rated_power_mw == "5.6"
    assert hub_height_m == "120"


def test_sort_turbine_rows_by_name():
    rows = [
        ("Beta", "1.0", "80"),
        ("alpha", "2.0", "90"),
        ("Gamma", "-", "-"),
    ]

    sorted_rows = cli._sort_turbine_rows(rows, cli.SortBy.name)

    assert [row[0] for row in sorted_rows] == ["alpha", "Beta", "Gamma"]


def test_sort_turbine_rows_by_hub_height_missing_last():
    rows = [
        ("A", "1.0", "-"),
        ("B", "1.0", "120"),
        ("C", "1.0", "80"),
    ]

    sorted_rows = cli._sort_turbine_rows(rows, cli.SortBy.hub_height)

    assert [row[0] for row in sorted_rows] == ["B", "C", "A"]


def test_sort_turbine_rows_by_power_missing_last():
    rows = [
        ("A", "-", "100"),
        ("B", "2.5", "100"),
        ("C", "0.5", "100"),
    ]

    sorted_rows = cli._sort_turbine_rows(rows, cli.SortBy.power)

    assert [row[0] for row in sorted_rows] == ["B", "C", "A"]


def test_list_turbines_default_sort_is_power_descending(monkeypatch):
    monkeypatch.setattr(
        cli,
        "get_turbine_catalog",
        lambda: {"atlite": [], "custom_turbines": ["Low", "High"]},
    )

    def fake_metrics(path):
        name = path.stem
        if name == "High":
            return "2", "100"
        return "0.5", "100"

    monkeypatch.setattr(cli, "_turbine_metrics_from_file", fake_metrics)

    result = runner.invoke(cli.app, ["list-turbines"])

    assert result.exit_code == 0
    assert result.output.index("High") < result.output.index("Low")


def test_list_turbines_invalid_sort_value():
    result = runner.invoke(cli.app, ["list-turbines", "--sort", "invalid"])

    assert result.exit_code != 0
    plain_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "Invalid value for '--sort'" in plain_output


def test_source_document_text_trims_and_links():
    long_source = "https://example.com/" + ("a" * 80)

    text = cli._source_document_text(long_source)

    assert text.plain == long_source[:40] + "..."
    assert len(text.spans) == 1
    assert long_source in text.spans[0].style


def test_inspect_turbine_command(monkeypatch):
    monkeypatch.setattr(
        cli,
        "inspect_turbine",
        lambda name: {
            "status": "ok",
            "turbine": name,
            "metadata": {
                "name": "DemoTurbine",
                "provider": "custom",
                "manufacturer": "ACME",
                "source": "local",
                "hub_height_m": 120.0,
                "rated_power_mw": 5.6,
                "definition_file": "config/wind/DemoTurbine.yaml",
            },
            "curve": [
                {"speed": 0.0, "power_mw": 0.0},
                {"speed": 10.0, "power_mw": 5.0},
                {"speed": 25.0, "power_mw": 5.6},
            ],
            "curve_summary": {"point_count": 3, "speed_min": 0.0, "speed_max": 25.0},
        },
    )

    result = runner.invoke(cli.app, ["inspect-turbine", "DemoTurbine"])

    assert result.exit_code == 0
    assert "DemoTurbine" in result.output
    assert "Power Curve" in result.output
    assert "Provider" in result.output
    assert "custom" in result.output


def test_inspect_turbine_command_not_found(monkeypatch):
    monkeypatch.setattr(
        cli,
        "inspect_turbine",
        lambda name: (_ for _ in ()).throw(ValueError("missing")),
    )

    result = runner.invoke(cli.app, ["inspect-turbine", "Unknown"])

    assert result.exit_code != 0
    assert "missing" in result.output


def test_list_solar_technologies_pretty_output(monkeypatch):
    monkeypatch.setattr(
        cli,
        "get_solar_catalog",
        lambda: {"atlite": ["CSi"], "custom_solar_technologies": ["MyPanel"]},
    )

    result = runner.invoke(cli.app, ["list-solar-technologies"])

    assert result.exit_code == 0
    assert "Solar" in result.output
    assert "(atlite)" in result.output
    assert "(custom)" in result.output
    assert "CSi" in result.output
    assert "MyPanel" in result.output
    assert "Source (atlite): live" in result.output
    assert "Source (custom): local" in result.output


def test_list_solar_technologies_no_items(monkeypatch):
    monkeypatch.setattr(
        cli,
        "get_solar_catalog",
        lambda: {"atlite": [], "custom_solar_technologies": []},
    )

    result = runner.invoke(cli.app, ["list-solar-technologies"])

    assert result.exit_code == 0
    assert "No solar technologies found." in result.output


def test_inspect_solar_technology_command(monkeypatch):
    monkeypatch.setattr(
        cli,
        "inspect_solar_technology",
        lambda name: {
            "status": "ok",
            "technology": name,
            "metadata": {
                "name": "MyPanel",
                "provider": "custom",
                "manufacturer": "ACME",
                "source": "local",
                "definition_file": "config/solar/MyPanel.yaml",
            },
            "parameters": {"A": 1.0, "B": 2.0},
        },
    )

    result = runner.invoke(cli.app, ["inspect-solar-technology", "MyPanel"])

    assert result.exit_code == 0
    assert "MyPanel" in result.output
    assert "Panel Parameters" in result.output
    assert "Provider" in result.output
    assert "custom" in result.output


def test_inspect_solar_technology_command_not_found(monkeypatch):
    monkeypatch.setattr(
        cli,
        "inspect_solar_technology",
        lambda name: (_ for _ in ()).throw(ValueError("missing solar")),
    )

    result = runner.invoke(cli.app, ["inspect-solar-technology", "UnknownPanel"])

    assert result.exit_code != 0
    assert "missing solar" in result.output
