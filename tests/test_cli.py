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
    assert "Invalid value for '--sort'" in result.output


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
                "definition_file": "custom_turbines/DemoTurbine.yaml",
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
    assert "Power (MW) vs Wind Speed (m/s)" in result.output


def test_inspect_turbine_command_not_found(monkeypatch):
    monkeypatch.setattr(
        cli,
        "inspect_turbine",
        lambda name: (_ for _ in ()).throw(ValueError("missing")),
    )

    result = runner.invoke(cli.app, ["inspect-turbine", "Unknown"])

    assert result.exit_code != 0
    assert "missing" in result.output
