# Renewables Profiles Generator

A Python tool for generating renewable energy profiles (wind and solar) from ERA5 weather data using the atlite library.

## Features

- **Wind Profile Generation**: Generate capacity factor time series for various turbine models
- **Solar Profile Generation**: Generate PV capacity factor time series with configurable panel orientations
- **Multiple Weather Years**: Support for historical weather data (1987, 2012, 2021-2024)
- **caching**: looks for the existing .csv file to avoid recomputing timeseries
- **Visualization**: Built-in plotting capabilities for profile analysis
- **Custom Turbines**: Support for custom turbine models via YAML configuration

## Setup

### Prerequisites
- Python ≥3.12
- [UV](https://docs.astral.sh/uv/) package manager
- ERA5 weather data cutout files (NetCDF format)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd renewables-profiles-generator
```

2. Setup virtual environment and install dependencies with UV:
```bash
uv sync
```

This will automatically create a virtual environment and install all required dependencies from the `pyproject.toml` file.

## Required Data

You need ERA5 weather data cutout files in NetCDF format. The default configuration expects files named:
- `europe-1987-era5.nc`
- `europe-2012-era5.nc`
- `europe-2021-era5.nc`
- `europe-2022-era5.nc`
- `europe-2023-era5.nc`
- `europe-2024-era5.nc`

Update the `base_path` in your configuration to point to your data directory. For the energy system studies group these are located on our teams environment under `\Energiesysteemstudies\11. Algemene gedeelde bestanden\ERA5 Data`

## Usage

### Basic Usage

1. Edit the configuration variables in `main.py`:
```python
# General configuration
PROFILE_TYPE = "both"  # Options: "wind", "solar", "both"
LATITUDE = 51.4713     # Your location latitude
LONGITUDE = 5.4186     # Your location longitude
OUTPUT_DIR = "project_name"

# Update data path
base_path=Path("/path/to/your/data")
```

2. Run the generator:
```bash
uv run python main.py
```

### Configuration Options

#### Wind Configuration
```python
TURBINE_MODEL = "NREL_ReferenceTurbine_2020ATB_4MW"
```

List available turbine models:
```python
from core.cutout_processing import get_available_turbine_list
print(get_available_turbine_list())
```

#### Solar Configuration
```python
SLOPES = [35, 15, 15]        # Panel tilt angles in degrees
AZIMUTHS = [180, 90, 270]    # Panel orientations (180=south, 90=east, 270=west)
PANEL_MODEL = "CSi"          # Panel technology
```

### Running and visualizing

```python
from core.profile_generator import ProfileGenerator, ProfileConfig, WindConfig, SolarConfig
from pathlib import Path

# Create custom configuration
profile_config = ProfileConfig(
    location={"lat": 52.705, "lon": 4.770},
    base_path=Path("/path/to/data"),
    output_dir=Path("output"),
    cutouts=[Path("europe-2024-era5.nc")]  # Use specific years
)

wind_config = WindConfig(turbine_model="NREL_ReferenceTurbine_2020ATB_4MW")
solar_config = SolarConfig(slopes=[30], azimuths=[180])

# Generate profiles
generator = ProfileGenerator(profile_config, wind_config, solar_config)
wind_profiles = generator.generate_wind_profiles()
solar_profiles = generator.generate_solar_profiles()

# Visualize results
generator.visualize_wind_profiles()
generator.visualize_solar_profiles_monthly()
```

## Output

Generated profiles are saved as CSV files in the specified output directory:

```
output_directory/
├── wind_profiles/
│   ├── 2024_NREL_ReferenceTurbine_2020ATB_4MW.csv
│   └── ...
└── solar_profiles/
    ├── 2024_slope30_azimuth180.csv
    └── ...
```

Each CSV file contains hourly capacity factor time series (values between 0 and 1). Depending on your specific application, you should multiply these with the installed capacity of the system under your consideration.

## Custom Turbines

Add custom turbine models by placing YAML files in the `custom_turbines/` directory. See existing examples for the required format.

## Dependencies

- atlite: Renewable energy calculations
- pandas: Data manipulation
- plotly: Visualization
- pydantic: Configuration validation
- numpy: Numerical operations
