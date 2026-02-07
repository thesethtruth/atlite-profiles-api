from pathlib import Path
from typing import Annotated

import typer

from service.runner import get_available_turbines, run_profiles

app = typer.Typer(help="Generate renewable profiles from ERA5 cutouts.")


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
def list_turbines() -> None:
    for turbine in get_available_turbines():
        typer.echo(turbine)


if __name__ == "__main__":
    app()
