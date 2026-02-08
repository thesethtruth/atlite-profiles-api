from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.catalog import (
    configure_downstream_warning_filters,
    fetch_atlite_solar_paths,
    fetch_atlite_turbine_paths,
)
from core.technology import (
    to_float as _to_float,
)
from core.technology import (
    turbine_metrics_from_file as _turbine_metrics_numeric,
)
from service.logging_utils import configure_logging
from service.runner import (
    fetch_cutouts,
    get_solar_catalog,
    get_turbine_catalog,
    inspect_solar_technology,
    inspect_turbine,
    run_profiles,
)

configure_logging()

app = typer.Typer(help="Generate renewable profiles from ERA5 cutouts.")
console = Console()


class SortBy(str, Enum):
    name = "name"
    hub_height = "hub_height"
    power = "power"


def _format_number(value: float | None, *, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _to_sort_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _turbine_metrics_from_file(path: Path | None) -> tuple[str, str]:
    rated_power, hub_height = _turbine_metrics_numeric(path)
    return _format_number(rated_power), _format_number(hub_height, digits=1)


def _sort_turbine_rows(
    rows: list[tuple[str, str, str]], sort_by: SortBy
) -> list[tuple[str, str, str]]:
    if sort_by is SortBy.name:
        return sorted(rows, key=lambda row: row[0].casefold())
    if sort_by is SortBy.hub_height:
        return sorted(
            rows,
            key=lambda row: (
                _to_sort_float(row[2]) is None,
                -(_to_sort_float(row[2]) or 0.0),
                row[0].casefold(),
            ),
        )
    return sorted(
        rows,
        key=lambda row: (
            _to_sort_float(row[1]) is None,
            -(_to_sort_float(row[1]) or 0.0),
            row[0].casefold(),
        ),
    )


def _atlite_turbine_files() -> dict[str, Path]:
    try:
        configure_downstream_warning_filters()
    except Exception:
        return {}
    return fetch_atlite_turbine_paths()


def _atlite_solar_files() -> dict[str, Path]:
    try:
        configure_downstream_warning_filters()
    except Exception:
        return {}
    return fetch_atlite_solar_paths()


def _render_power_curve_chart(
    curve: list[dict[str, float]], *, width: int = 46, height: int = 14
) -> Text | str:
    if not curve:
        return "No power curve points found."

    points = sorted(curve, key=lambda point: point["speed"])
    x_values = [point["speed"] for point in points]
    y_values = [point["power_mw"] for point in points]

    try:
        import plotext as plt
    except Exception:
        return _render_power_curve_chart_ascii(curve, width=width, height=height)

    try:
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        x_span = x_max - x_min if x_max > x_min else 1.0
        y_span = y_max - y_min if y_max > y_min else 1.0
        x_pad = max(0.2, x_span * 0.04)
        y_pad = max(0.05, y_span * 0.08)

        plt.clear_figure()
        plt.theme("clear")
        plt.canvas_color("default")
        plt.axes_color("default")
        plt.ticks_color("white")
        plt.plotsize(max(36, width), max(12, height))
        plt.frame(False)
        plt.xaxes(lower=True, upper=False)
        plt.yaxes(left=True, right=False)
        plt.grid(horizontal=False, vertical=False)
        plt.xfrequency(6)
        plt.yfrequency(5)
        plt.xlim(0, x_max + x_pad)
        plt.ylim(max(0.0, y_min - y_pad), y_max + y_pad)
        plt.plot(x_values, y_values, marker="dot", color="cyan", style="bold")
        plt.scatter(x_values, y_values, marker="x", color="red")
        rendered = plt.build()
        chart = Text()
        chart.append("Power (MW)\n", style="bold green")
        chart.append(Text.from_ansi(rendered))
        chart.append("\n\t\t\t\tWind Speed (m/s)\n", style="bold green")

        return chart
    except Exception:
        return _render_power_curve_chart_ascii(curve, width=width, height=height)
    finally:
        try:
            plt.clear_figure()
        except Exception:
            pass


def _with_vertical_y_label(rendered_plot: str, label: str) -> str:
    lines = rendered_plot.splitlines()
    if not lines or not label:
        return rendered_plot

    prefixes = [" "] * len(lines)
    start = max(0, (len(lines) - len(label)) // 2)
    for idx, char in enumerate(label):
        target = start + idx
        if target >= len(prefixes):
            break
        prefixes[target] = char

    return "\n".join(
        f"{prefixes[line_idx]} {line}" for line_idx, line in enumerate(lines)
    )


def _render_power_curve_chart_ascii(
    curve: list[dict[str, float]], *, width: int = 46, height: int = 14
) -> Text | str:
    if not curve:
        return "No power curve points found."

    x_values = [point["speed"] for point in curve]
    y_values = [point["power_mw"] for point in curve]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)

    x_span = x_max - x_min if x_max > x_min else 1.0
    y_span = y_max - y_min if y_max > y_min else 1.0
    plot = [[" "] * width for _ in range(height)]

    for point in curve:
        x_index = int(round(((point["speed"] - x_min) / x_span) * (width - 1)))
        y_index = int(round(((point["power_mw"] - y_min) / y_span) * (height - 1)))
        row = height - 1 - y_index
        plot[row][x_index] = "●"

    lines: list[str] = []
    for index, row in enumerate(plot):
        y_axis_value = y_max - ((y_span * index) / max(height - 1, 1))
        lines.append(f"{y_axis_value:>6.2f} |{''.join(row)}")

    x_line = " " * 7 + "+" + ("-" * width)
    x_labels = (
        f"{'':>7}{x_min:.1f} m/s"
        f"{' ' * max(1, width - len(f'{x_min:.1f} m/s') - len(f'{x_max:.1f} m/s'))}"
        f"{x_max:.1f} m/s"
    )
    chart = Text()
    chart.append("\t\tPower (MW) vs Wind Speed (m/s)\n\n", style="bold green")
    for line in lines:
        chart.append(line)
        chart.append("\n")
    chart.append(x_line)
    chart.append("\n")
    chart.append(x_labels)
    return chart


def _source_document_text(value: object) -> Text:
    source = str(value)
    if len(source) == 0:
        return Text("-")
    label = source[:40]
    if len(source) > 40:
        label += "..."
    text = Text(label)
    if source.startswith(("http://", "https://")):
        text.stylize(f"link {source}", 0, len(label))
    return text


def _turbine_metadata_table(payload: dict[str, object]) -> Table:
    metadata = payload["metadata"]
    curve_summary = payload["curve_summary"]
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold cyan")
    table.add_column()

    table.add_row("Name", str(metadata["name"]))
    table.add_row("Provider", str(metadata["provider"]))
    table.add_row("Manufacturer", str(metadata["manufacturer"]))
    table.add_row("Source", _source_document_text(metadata["source"]))
    table.add_row(
        "Hub Height",
        f"{_format_number(_to_float(metadata['hub_height_m']), digits=1)} m",
    )
    table.add_row(
        "Rated Power", f"{_format_number(_to_float(metadata['rated_power_mw']))} MW"
    )
    table.add_row("Curve Points", str(curve_summary["point_count"]))
    table.add_row(
        "Speed Range",
        (
            f"{_format_number(_to_float(curve_summary['speed_min']), digits=1)} - "
            f"{_format_number(_to_float(curve_summary['speed_max']), digits=1)} m/s"
        ),
    )
    table.add_row("Definition", str(metadata["definition_file"]))
    return table


def _solar_metadata_table(payload: dict[str, object]) -> Table:
    metadata = payload["metadata"]
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Name", str(metadata["name"]))
    table.add_row("Provider", str(metadata["provider"]))
    table.add_row("Manufacturer", str(metadata["manufacturer"]))
    table.add_row("Source", _source_document_text(metadata["source"]))
    table.add_row("Definition", str(metadata["definition_file"]))
    return table


def _solar_parameters_table(payload: dict[str, object]) -> Table:
    parameters = payload["parameters"]
    table = Table(
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Parameter", overflow="fold")
    table.add_column("Value", overflow="fold")
    for key in sorted(parameters):
        table.add_row(str(key), str(parameters[key]))
    return table


def _load_yaml_mapping(path: Path, *, param_hint: str, label: str) -> dict[str, object]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise typer.BadParameter(str(exc), param_hint=param_hint)
    if not isinstance(loaded, dict):
        raise typer.BadParameter(
            f"{label} YAML must contain an object.",
            param_hint=param_hint,
        )
    return loaded


def _format_validation_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "-"
    return str(value)


def _validation_metadata_table(metadata: dict[str, object]) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold cyan")
    table.add_column(overflow="fold")
    for key in ("module", "x", "y", "time", "features"):
        table.add_row(key, _format_validation_value(metadata.get(key)))
    return table


def _render_validation_report_details(validation_report: dict[str, object]) -> None:
    entries = validation_report.get("entries")
    if not isinstance(entries, list) or len(entries) == 0:
        return

    console.print()
    console.print("[bold]Validation details:[/bold]")
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        expected = entry.get("expected")
        observed = entry.get("observed")
        if not isinstance(expected, dict):
            expected = {}
        if not isinstance(observed, dict):
            observed = {}

        entry_name = str(entry.get("name") or entry.get("filename") or "cutout")
        status = str(entry.get("status") or "unknown")
        path = str(entry.get("path") or "-")

        left_card = Panel(
            _validation_metadata_table(expected),
            title="Config (Expected)",
            border_style="cyan",
            expand=True,
        )

        right_content: Table | str = _validation_metadata_table(observed)
        if status == "missing":
            right_content = f"Local cutout missing at {path}"
        elif status == "remote_skipped":
            right_content = f"Remote target skipped: {path}"
        elif status == "error":
            right_content = f"Validation error: {entry.get('error', '-')}"
        border_style = "green" if status == "match" else "yellow"
        if status == "mismatch":
            border_style = "red"
        right_card = Panel(
            right_content,
            title=f"Found ({status})",
            border_style=border_style,
            expand=True,
        )

        console.print(f"[bold]{entry_name}[/bold] ({status})")
        console.print(Columns([left_card, right_card], equal=True, expand=True))
        if status == "mismatch":
            mismatches = entry.get("mismatches")
            if isinstance(mismatches, list) and mismatches:
                console.print("[yellow]Mismatches:[/yellow]")
                for mismatch in mismatches:
                    console.print(f"- {mismatch}")
        console.print(f"[dim]Path:[/dim] {path}")
        console.print()


@app.command("generate")
def generate(
    profile_type: Annotated[
        str,
        typer.Option(help="Profile type: wind, solar, or both."),
    ] = "both",
    latitude: Annotated[float, typer.Option(help="Location latitude.")] = 51.4713,
    longitude: Annotated[float, typer.Option(help="Location longitude.")] = 5.4186,
    base_path: Annotated[
        Path,
        typer.Option(help="Directory containing cutout NetCDF files."),
    ] = Path("data"),
    output_dir: Annotated[Path, typer.Option(help="Output directory.")] = Path(
        "output"
    ),
    cutout: Annotated[
        list[str],
        typer.Option(help="Cutout file name(s). Repeat --cutout for multiple."),
    ] = ["europe-2024-era5.nc"],
    turbine_model: Annotated[str, typer.Option(help="Wind turbine model name.")] = (
        "NREL_ReferenceTurbine_2020ATB_4MW"
    ),
    turbine_config_file: Annotated[
        Path | None,
        typer.Option(
            help="Path to a custom wind turbine config YAML file.",
        ),
    ] = None,
    slope: Annotated[
        list[float],
        typer.Option(help="Solar slope value(s). Repeat --slope for multiple."),
    ] = [30.0],
    azimuth: Annotated[
        list[float],
        typer.Option(help="Solar azimuth value(s). Repeat --azimuth for multiple."),
    ] = [180.0],
    panel_model: Annotated[str, typer.Option(help="Solar panel model.")] = "CSi",
    solar_technology_config_file: Annotated[
        Path | None,
        typer.Option(
            help="Path to a custom solar technology config YAML file.",
        ),
    ] = None,
    visualize: Annotated[bool, typer.Option(help="Display plots.")] = False,
) -> None:
    turbine_config: dict[str, object] | None = None
    if turbine_config_file is not None:
        turbine_config = _load_yaml_mapping(
            turbine_config_file,
            param_hint="turbine-config-file",
            label="Turbine config",
        )

    solar_technology_config: dict[str, object] | None = None
    if solar_technology_config_file is not None:
        solar_technology_config = _load_yaml_mapping(
            solar_technology_config_file,
            param_hint="solar-technology-config-file",
            label="Solar technology config",
        )

    result = run_profiles(
        profile_type=profile_type,
        latitude=latitude,
        longitude=longitude,
        base_path=base_path,
        output_dir=output_dir,
        cutouts=cutout,
        turbine_model=turbine_model,
        turbine_config=turbine_config,
        slopes=slope,
        azimuths=azimuth,
        panel_model=panel_model,
        solar_technology_config=solar_technology_config,
        visualize=visualize,
    )
    typer.echo(
        "Done: "
        f"wind={result['wind_profiles']}, "
        f"solar={result['solar_profiles']}, "
        f"output={result['output_dir']}"
    )


@app.command("list-turbines")
def list_turbines(
    sort: Annotated[
        SortBy,
        typer.Option("--sort", help="Sort rows by: name, hub_height, or power."),
    ] = SortBy.power,
) -> None:
    catalog = get_turbine_catalog()
    atlite_turbines = catalog["atlite"]
    custom_turbines = catalog["custom_turbines"]

    if len(atlite_turbines) + len(custom_turbines) == 0:
        console.print("[yellow]No turbines found.[/yellow]")
        return

    atlite_table = Table(
        title="Available Turbines (atlite)",
        show_header=True,
        header_style="bold magenta",
    )
    atlite_table.add_column("#", justify="right")
    atlite_table.add_column("Turbine", overflow="fold")
    atlite_table.add_column("Rated power (MW)", justify="right")
    atlite_table.add_column("Hub height (m)", justify="right")
    atlite_files = _atlite_turbine_files()
    atlite_rows: list[tuple[str, str, str]] = []
    for turbine in atlite_turbines:
        rated_power_mw, hub_height_m = _turbine_metrics_from_file(
            atlite_files.get(turbine)
        )
        atlite_rows.append((turbine, rated_power_mw, hub_height_m))
    for index, (turbine, rated_power_mw, hub_height_m) in enumerate(
        _sort_turbine_rows(atlite_rows, sort), start=1
    ):
        atlite_table.add_row(str(index), turbine, rated_power_mw, hub_height_m)
    console.print()
    console.print(atlite_table)
    console.print("[green]Source (atlite):[/green] live")
    console.print()

    custom_table = Table(
        title="Available Turbines (custom)",
        show_header=True,
        header_style="bold magenta",
    )
    custom_table.add_column("#", justify="right")
    custom_table.add_column("Turbine", overflow="fold")
    custom_table.add_column("Rated power (MW)", justify="right")
    custom_table.add_column("Hub height (m)", justify="right")
    custom_rows: list[tuple[str, str, str]] = []
    for turbine in custom_turbines:
        rated_power_mw, hub_height_m = _turbine_metrics_from_file(
            Path("config/wind") / f"{turbine}.yaml"
        )
        custom_rows.append((turbine, rated_power_mw, hub_height_m))
    for index, (turbine, rated_power_mw, hub_height_m) in enumerate(
        _sort_turbine_rows(custom_rows, sort), start=1
    ):
        custom_table.add_row(str(index), turbine, rated_power_mw, hub_height_m)
    console.print(custom_table)
    console.print()
    console.print("[green]Source (custom):[/green] local")


@app.command("list-solar-technologies")
def list_solar_technologies() -> None:
    catalog = get_solar_catalog()
    atlite_technologies = catalog["atlite"]
    custom_technologies = catalog["custom_solar_technologies"]

    if len(atlite_technologies) + len(custom_technologies) == 0:
        console.print("[yellow]No solar technologies found.[/yellow]")
        return

    atlite_table = Table(
        title="Available Solar Technologies (atlite)",
        show_header=True,
        header_style="bold magenta",
    )
    atlite_table.add_column("#", justify="right")
    atlite_table.add_column("Technology", overflow="fold")
    for index, technology in enumerate(sorted(atlite_technologies), start=1):
        atlite_table.add_row(str(index), technology)
    console.print()
    console.print(atlite_table)
    console.print("[green]Source (atlite):[/green] live")
    console.print()

    custom_table = Table(
        title="Available Solar Technologies (custom)",
        show_header=True,
        header_style="bold magenta",
    )
    custom_table.add_column("#", justify="right")
    custom_table.add_column("Technology", overflow="fold")
    for index, technology in enumerate(sorted(custom_technologies), start=1):
        custom_table.add_row(str(index), technology)
    console.print(custom_table)
    console.print()
    console.print("[green]Source (custom):[/green] local")


@app.command("inspect-turbine")
def inspect_turbine_command(
    turbine_model: Annotated[
        str, typer.Argument(help="Turbine model name to inspect.")
    ],
) -> None:
    try:
        payload = inspect_turbine(turbine_model)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="turbine-model")

    metadata = payload["metadata"]
    chart = _render_power_curve_chart(payload["curve"])
    left_card = Panel(
        _turbine_metadata_table(payload),
        title=str(metadata["name"]),
        border_style="cyan",
        expand=True,
    )
    right_card = Panel(
        chart,
        title="Power Curve",
        border_style="green",
        expand=True,
    )
    console.print("\n")
    console.print(
        Columns(
            [left_card, right_card],
            equal=True,
            expand=True,
        )
    )


@app.command("inspect-solar-technology")
def inspect_solar_technology_command(
    technology: Annotated[
        str, typer.Argument(help="Solar technology name to inspect.")
    ],
) -> None:
    try:
        payload = inspect_solar_technology(technology)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="technology")

    metadata = payload["metadata"]
    left_card = Panel(
        _solar_metadata_table(payload),
        title=str(metadata["name"]),
        border_style="cyan",
        expand=True,
    )
    right_card = Panel(
        _solar_parameters_table(payload),
        title="Panel Parameters",
        border_style="green",
        expand=True,
    )
    console.print("\n")
    console.print(
        Columns(
            [left_card, right_card],
            equal=True,
            expand=True,
        )
    )


@app.command("fetch-cutouts")
def fetch_cutouts_command(
    config_file: Annotated[
        Path | None,
        typer.Option(
            help="Path to a cutout-fetch config YAML (expects a top-level 'cutouts')."
        ),
    ] = None,
    all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Use config/cutouts.yaml and process all configured cutouts.",
        ),
    ] = False,
    force_refresh: Annotated[
        bool,
        typer.Option(
            help="Regenerate and overwrite existing cutouts (and re-upload for remote)."
        ),
    ] = False,
    name: Annotated[
        str | None,
        typer.Option(
            help="Only process the cutout entry with matching YAML 'name'.",
        ),
    ] = None,
    report_validate_existing: Annotated[
        bool,
        typer.Option(
            help=(
                "Inspect local existing .nc files and print a compatibility report at "
                "the end."
            )
        ),
    ] = False,
) -> None:
    if config_file is None and not all:
        raise typer.BadParameter(
            "Provide --config-file or use --all.",
            param_hint="config-file",
        )
    if config_file is not None and all:
        raise typer.BadParameter(
            "Use either --config-file or --all, not both.",
            param_hint="all",
        )

    if config_file is not None:
        resolved_config = config_file
    else:
        resolved_config = Path("config/cutouts.yaml")
    try:
        result = fetch_cutouts(
            config_file=resolved_config,
            force_refresh=force_refresh,
            name=name,
            report_validate_existing=report_validate_existing,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="config-file")

    typer.echo(
        "Done: "
        f"fetched={result['fetched_count']}, "
        f"skipped={result['skipped_count']}, "
        f"config={resolved_config}"
    )
    validation_report = result.get("validation_report")
    if isinstance(validation_report, dict):
        typer.echo(
            "Validation report: "
            f"checked={validation_report['checked']}, "
            f"matched={validation_report['matched']}, "
            f"mismatched={validation_report['mismatched']}, "
            f"missing={validation_report['missing']}, "
            f"remote_skipped={validation_report['remote_skipped']}, "
            f"errors={validation_report['errors']}"
        )
        _render_validation_report_details(validation_report)


if __name__ == "__main__":
    app()
