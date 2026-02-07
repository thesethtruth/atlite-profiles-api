from pathlib import Path
from enum import Enum
from typing import Annotated

import typer
import yaml
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


from service.runner import (
    _configure_downstream_warning_filters,
    get_turbine_catalog,
    inspect_turbine,
    run_profiles,
)

app = typer.Typer(help="Generate renewable profiles from ERA5 cutouts.")
console = Console()


class SortBy(str, Enum):
    name = "name"
    hub_height = "hub_height"
    power = "power"


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_number(value: float | None, *, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _value_to_mw(value: float) -> float:
    # Turbine YAMLs can store power in kW (e.g. 5600) or MW (e.g. 5.6).
    if value > 100:
        return value / 1000.0
    return value


def _to_sort_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _rated_power_mw(payload: dict[str, object]) -> float | None:
    p_value = _to_float(payload.get("P"))
    pow_values = payload.get("POW")
    max_pow: float | None = None
    if isinstance(pow_values, list):
        float_values = [
            float(item) for item in pow_values if isinstance(item, (int, float))
        ]
        if float_values:
            max_pow = max(float_values)

    if p_value is not None:
        return _value_to_mw(p_value)
    if max_pow is not None:
        return _value_to_mw(max_pow)
    return None


def _turbine_metrics_from_file(path: Path | None) -> tuple[str, str]:
    if path is None or not path.exists():
        return "-", "-"
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        return "-", "-"
    if not isinstance(payload, dict):
        return "-", "-"

    rated_power = _rated_power_mw(payload)
    hub_height = _to_float(payload.get("HUB_HEIGHT"))
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
        _configure_downstream_warning_filters()
        import atlite.resource
    except Exception:
        return {}
    return {name: Path(path) for name, path in atlite.resource.windturbines.items()}


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
        f"{_format_number(_to_float(curve_summary['speed_min']), digits=1)} - {_format_number(_to_float(curve_summary['speed_max']), digits=1)} m/s",
    )
    table.add_row("Definition", str(metadata["definition_file"]))
    return table


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
    slope: Annotated[
        list[float],
        typer.Option(help="Solar slope value(s). Repeat --slope for multiple."),
    ] = [30.0],
    azimuth: Annotated[
        list[float],
        typer.Option(help="Solar azimuth value(s). Repeat --azimuth for multiple."),
    ] = [180.0],
    panel_model: Annotated[str, typer.Option(help="Solar panel model.")] = "CSi",
    visualize: Annotated[bool, typer.Option(help="Display plots.")] = False,
) -> None:
    result = run_profiles(
        profile_type=profile_type,
        latitude=latitude,
        longitude=longitude,
        base_path=base_path,
        output_dir=output_dir,
        cutouts=cutout,
        turbine_model=turbine_model,
        slopes=slope,
        azimuths=azimuth,
        panel_model=panel_model,
        visualize=visualize,
    )
    typer.echo(
        f"Done: wind={result['wind_profiles']}, solar={result['solar_profiles']}, output={result['output_dir']}"
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
            Path("custom_turbines") / f"{turbine}.yaml"
        )
        custom_rows.append((turbine, rated_power_mw, hub_height_m))
    for index, (turbine, rated_power_mw, hub_height_m) in enumerate(
        _sort_turbine_rows(custom_rows, sort), start=1
    ):
        custom_table.add_row(str(index), turbine, rated_power_mw, hub_height_m)
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


if __name__ == "__main__":
    app()
