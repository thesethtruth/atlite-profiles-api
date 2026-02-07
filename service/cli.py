from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from service.runner import get_turbine_catalog_with_source, run_profiles

app = typer.Typer(help="Generate renewable profiles from ERA5 cutouts.")
console = Console()


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
    force_update: Annotated[
        bool,
        typer.Option(
            "--force-update",
            help="Refresh turbine list from source and overwrite cache.",
        ),
    ] = False,
) -> None:
    catalog, source = get_turbine_catalog_with_source(force_update=force_update)
    atlite_turbines = catalog["atlite"]
    custom_turbines = catalog["custom_turbines"]

    if len(atlite_turbines) + len(custom_turbines) == 0:
        console.print(
            "[yellow]No cached turbines found. Run with --force-update once to populate cache.[/yellow]"
        )
        return

    atlite_table = Table(
        title="Available Turbines (atlite)", show_header=True, header_style="bold magenta"
    )
    atlite_table.add_column("#", justify="right")
    atlite_table.add_column("Turbine", overflow="fold")
    for index, turbine in enumerate(atlite_turbines, start=1):
        atlite_table.add_row(str(index), turbine)
    console.print()
    console.print(atlite_table)
    atlite_source = "cache"
    if source == "refreshed":
        atlite_source = "refreshed"
    elif source == "cache-miss":
        atlite_source = "missing"
    console.print(f"[green]Source (atlite):[/green] {atlite_source}")
    console.print()

    custom_table = Table(
        title="Available Turbines (custom)",
        show_header=True,
        header_style="bold magenta",
    )
    custom_table.add_column("#", justify="right")
    custom_table.add_column("Turbine", overflow="fold")
    for index, turbine in enumerate(custom_turbines, start=1):
        custom_table.add_row(str(index), turbine)
    console.print(custom_table)
    console.print()
    console.print("[green]Source (custom):[/green] local")


if __name__ == "__main__":
    app()
