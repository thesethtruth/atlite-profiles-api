import logging
from pathlib import Path

import atlite
import atlite.resource
import numpy as np
import pandas as pd
import xarray as xr
import yaml

logger = logging.getLogger(__name__)


def get_wind_profile(
    lat: float,
    lon: float,
    cutout_path: Path,
    turbine: str | dict[str, object],
):
    """Generate wind profile time series for one location and turbine."""

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

    logger.info("Calculating wind resource for turbine %s", turbine)
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
    cutout_path: Path,
    slope: float = 30,
    azimuth: float = 180,
    panel_model: str | dict[str, object] = "CSi",
) -> pd.Series:
    """Generate solar profile time series for one location and orientation."""

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

    # Add custom turbines from config/wind folder
    custom_turbines_dir = Path("config/wind")
    if custom_turbines_dir.exists():
        for yaml_file in custom_turbines_dir.glob("*.yaml"):
            # Remove .yaml extension to get turbine name
            turbine_name = yaml_file.stem
            available_turbines.append(turbine_name)

    return available_turbines


def get_available_solar_technology_list():
    """
    Get a list of pre-configured solar panel technologies including custom definitions.
    """
    solarpanels = atlite.resource.solarpanels
    available_technologies = list(solarpanels.keys())

    custom_dir = Path("config/solar")
    if custom_dir.exists():
        for yaml_file in custom_dir.glob("*.yaml"):
            available_technologies.append(yaml_file.stem)

    return available_technologies


def get_turbine_data(turbine_model: str):
    """Print the data for a specific turbine model.
    Parameters:

    turbine_model (str): The name of the turbine model.
    """
    windturbines = atlite.resource.windturbines
    fp: Path = windturbines[turbine_model]
    with open(fp) as f:
        data = yaml.safe_load(f)
    logger.info("Loaded turbine data for '%s'", turbine_model)
    return data


def get_solar_technology_data(technology: str):
    """Print the data for a specific solar technology."""
    solarpanels = atlite.resource.solarpanels
    fp: Path = solarpanels[technology]
    with open(fp) as f:
        data = yaml.safe_load(f)
    logger.info("Loaded solar technology data for '%s'", technology)
    return data
