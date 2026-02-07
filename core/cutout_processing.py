import atlite.resource
import xarray as xr
import atlite
import numpy as np
import pandas as pd
from pathlib import Path
import yaml


def get_wind_profile(
    lat: float,
    lon: float,
    cutout_path: Path,
    turbine: str | dict[str, object],
):
    """
    Calculate the wind generation profile for a given location and turbine model.
    Parameters:
    lat (float): Latitude of the location.
    lon (float): Longitude of the location.
    cutout_path (Path, optional): Path to the cutout file. Defaults to "data/europe-2023-era5.nc".
    turbine_model (str, optional): Turbine model to use for the wind profile calculation. Defaults to "NREL_ReferenceTurbine_2020ATB_15MW_offshore".
    Returns:
    pd.Series: A pandas Series containing the wind generation profile.
    Notes:
    - The function slices the cutout data around the given latitude and longitude.
    - It creates a mask to locate the nearest grid point in the cutout data.
    - The wind profile is calculated using the specified turbine model.
    - If the resulting wind profile contains data for a leap day, it is removed.
    """

    cutout = atlite.Cutout(cutout_path)
    lat_slice = slice(lat - 1.0, lat + 1.0)
    lon_slice = slice(lon - 1.0, lon + 1.0)
    sliced_cutout = cutout.sel(y=lat_slice, x=lon_slice)

    mask = xr.DataArray(
        np.zeros_like(cutout.data["height"]),
        coords=cutout.data["height"].coords,
        dims=cutout.data["height"].dims,
    )
    nearest_y = sliced_cutout.data["y"].sel(y=lat, method="nearest")
    nearest_x = sliced_cutout.data["x"].sel(x=lon, method="nearest")
    mask.loc[dict(x=nearest_x, y=nearest_y)] = 1

    print(f"Calculating wind resource for turbine {turbine}")
    wind_profile: pd.DataFrame = sliced_cutout.wind(
        turbine=turbine,
        layout=mask,
        per_unit=True,
        capacity_factor_timeseries=True,
        show_progress=True,
        add_cutout_windspeed=True,
    )
    wind_profile_df: pd.DataFrame = wind_profile.squeeze().to_dataframe(
        name="wind_generation"
    )

    # Check for leap day and remove it
    if len(wind_profile_df) == 8784:
        wind_profile_df = wind_profile_df[
            ~((wind_profile_df.index.month == 2) & (wind_profile_df.index.day == 29))
        ]

    return wind_profile_df["wind_generation"]


def get_solar_profile(
    lat: float,
    lon: float,
    slope: float = 30,
    azimuth: float = 180,
    cutout_path: Path = Path("data/europe-2023-era5.nc"),
    panel_model: str = "CSi",
) -> pd.Series:
    """
    Generate a solar generation profile for a given location and panel orientation.
    Parameters:
    lat (float): Latitude of the location.
    lon (float): Longitude of the location.
    slope (float, optional): Slope of the solar panel in degrees. Default is 30.
    azimuth (float, optional): Azimuth angle of the solar panel in degrees. Default is 180.
    cutout_path (Path, optional): Path to the cutout data file. Default is "data/europe-2023-era5.nc".
    panel_model (str, optional): Model of the solar panel. Default is "CSi".
    Returns:
    pandas.Series: A time series of solar generation values.
    Notes:
    - The function slices the cutout data around the specified latitude and longitude.
    - It creates a mask for the nearest grid point to the specified location.
    - The solar generation profile is calculated using the specified panel model and orientation.
    - If the resulting time series includes a leap day, it is removed.
    """

    cutout = atlite.Cutout(cutout_path)  # from RVO energiemix
    lat_slice = slice(lat - 0.5, lat + 0.5)
    lon_slice = slice(lon - 0.5, lon + 0.5)
    sliced_cutout = cutout.sel(y=lat_slice, x=lon_slice)

    mask = xr.DataArray(
        np.zeros_like(cutout.data["height"]),
        coords=cutout.data["height"].coords,
        dims=cutout.data["height"].dims,
    )
    nearest_y = sliced_cutout.data["y"].sel(y=lat, method="nearest")
    nearest_x = sliced_cutout.data["x"].sel(x=lon, method="nearest")
    mask.loc[dict(x=nearest_x, y=nearest_y)] = 1

    orientation = dict(slope=slope, azimuth=azimuth)
    solar_profile = sliced_cutout.pv(
        panel=panel_model,
        orientation=orientation,
        layout=mask,
        per_unit=True,
        capacity_factor_timeseries=True,
        show_progress=True,
    )
    solar_profile_df = solar_profile.squeeze().to_dataframe(name="solar_generation")

    # Check for leap day and remove it
    if len(solar_profile_df) == 8784:
        solar_profile_df = solar_profile_df[
            ~((solar_profile_df.index.month == 2) & (solar_profile_df.index.day == 29))
        ]

    return solar_profile_df["solar_generation"]


def get_available_turbine_list():
    """
    Get a list of pre-configured turbine models including custom turbines.
    """
    windturbines = atlite.resource.windturbines
    available_turbines = list(windturbines.keys())

    # Add custom turbines from custom_turbines folder
    custom_turbines_dir = Path("custom_turbines")
    if custom_turbines_dir.exists():
        for yaml_file in custom_turbines_dir.glob("*.yaml"):
            # Remove .yaml extension to get turbine name
            turbine_name = yaml_file.stem
            available_turbines.append(turbine_name)

    return available_turbines


def get_turbine_data(turbine_model: str):
    """Print the data for a specific turbine model.
    Parameters:

    turbine_model (str): The name of the turbine model.
    """
    windturbines = atlite.resource.windturbines
    fp: Path = windturbines[turbine_model]
    with open(fp) as f:
        data = yaml.safe_load(f)
    print(data)
    return data
