# Renewables Profiles Generator

This project generates wind and solar capacity-factor time series from ERA5 cutout files.

## Quick Start

```bash
uv sync --group dev
uv run pytest
uv run profiles-cli --help
uv run profiles-api
```

## Docker Quick Start

```bash
docker compose up --build
```

- API under Caddy: `http://localhost:8080/api/*`
- Docs under Caddy: `http://localhost:8080/docs`

## Project Areas

- `core/`: generation and cutout processing logic
- `service/`: Typer CLI + FastAPI API layer
- `tests/`: pytest suite
- `custom_turbines/`: custom turbine definitions

## Data Requirement

Provide ERA5 NetCDF cutouts (for example `europe-2024-era5.nc`) and pass their base directory as `base_path`.
