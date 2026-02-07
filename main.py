from pathlib import Path

from core.profile_generator import (
    ProfileGenerator,
    ProfileConfig,
    WindConfig,
    SolarConfig,
)
from core.cutout_processing import get_available_turbine_list

# Configuration variables
# You can modify these variables to customize the profile generation


# General configuration
PROFILE_TYPE = "both"  # Options: "wind", "solar", "both"
LATITUDE = 51.4713
LONGITUDE = 5.4186
VISUALIZE_RESULTS = True
OUTPUT_DIR = "project_name"

# Uncomment to list available turbines
# print(get_available_turbine_list())

# Wind-specific configuration
TURBINE_MODEL = "NREL_ReferenceTurbine_2020ATB_4MW"

# Solar-specific configuration
SLOPES = [35, 15, 15]
AZIMUTHS = [180, 90, 270]  # clockwise degrees from north i.e. 180 is south facing
PANEL_MODEL = "CSi"  # just leave this

# Create configurations
# base information
profile_config = ProfileConfig(
    location={"lat": LATITUDE, "lon": LONGITUDE},
    base_path=Path("data"),  # change this to your data path
    output_dir=Path(OUTPUT_DIR),
    cutouts=[
        # Path("europe-1987-era5.nc"),
        # Path("europe-2012-era5.nc"),
        # Path("europe-2021-era5.nc"),
        # Path("europe-2022-era5.nc"),
        # Path("europe-2023-era5.nc"),
        Path("europe-2024-era5.nc"),
    ],
)

# wind specific information
wind_config = WindConfig(turbine_model=TURBINE_MODEL)

# solar specific information
solar_config = SolarConfig(
    slopes=SLOPES,
    azimuths=AZIMUTHS,
    panel_model=PANEL_MODEL,
    output_subdir="solar_profiles",
)

# Create generator
generator = ProfileGenerator(
    profile_config=profile_config,
    wind_config=wind_config,
    solar_config=solar_config,
)

# Generate profiles
if PROFILE_TYPE in ["wind", "both"]:
    generator.generate_wind_profiles()
    if VISUALIZE_RESULTS:
        generator.visualize_wind_profiles()

if PROFILE_TYPE in ["solar", "both"]:
    generator.generate_solar_profiles()
if VISUALIZE_RESULTS:
    generator.visualize_solar_profiles_monthly(color_key="azimuth")
