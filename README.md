# Atlite profiles generator

A wrapper around [atlite](https://github.com/PyPSA/atlite) which exposes a CLI and/or API (hosted as service here) to improve your DX when working with generation profiles and reduce leadtime in small projects. Generate wind and solar capacity-factor time series from ERA5 cutout files using `atlite`.

## Overview

- Wind and solar profile generation from ERA5 NetCDF cutouts
- Typer CLI for local runs and turbine discovery
- Turbine inspection via `profiles-cli inspect-turbine`
- FastAPI service for API-based execution
- Optional inline API `turbine_config` for custom wind curves
- Support for local custom turbine YAMLs in `custom_turbines/`
- Automated `pytest` suite for runner, CLI, and API behavior
- Docker deployment with Caddy routing `/api` and `/docs`

## Project Layout

- `core/`: generation and cutout processing logic
- `service/`: CLI and API entrypoints/runtime integration
- `tests/`: automated tests
- `custom_turbines/`: local turbine definitions
- `docs/`: detailed user and interface documentation

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

## Documentation

- Overview: `docs/index.md`
- CLI reference: `docs/cli.md`
- API reference: `docs/api.md`
- Deployment: `docs/deployment.md`

Use the docs as the source of truth for command options, examples, and endpoint details.
For inline custom turbines in API requests, see `docs/api.md` (`turbine_config` on `POST /generate`).

Quick CLI inspection example:

```bash
uv run profiles-cli inspect-turbine Vestas_V162_5.6
```
