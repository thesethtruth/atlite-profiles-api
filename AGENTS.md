# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: Entry point for local profile generation runs.
- `core/profile_generator.py`: Configuration models (`ProfileConfig`, `WindConfig`, `SolarConfig`) and orchestration logic.
- `core/cutout_processing.py`: Low-level wind/solar extraction from atlite cutouts.
- `service/cli.py`: Typer CLI commands.
- `service/api.py`: FastAPI application and API entrypoint.
- `service/runner.py`: Shared execution layer used by CLI and API.
- `tests/`: `pytest` suite for CLI, API, and shared runtime behavior.
- `custom_turbines/*.yaml`: Custom turbine definitions loaded at runtime.
- `README.md`: Usage and setup reference.
- `pyproject.toml` and `uv.lock`: Dependency and environment lock files.

Keep domain logic in `core/`; keep `main.py` as a thin configuration and execution script.
Keep business/runtime behavior shared through `service/runner.py` so CLI and API expose the same features without duplicate implementations.

## Build, Test, and Development Commands
- `uv sync`: Create/update the virtual environment and install pinned dependencies.
- `uv run python main.py`: Run profile generation with values configured in `main.py`.
- `uv run profiles-cli --help`: Show CLI commands.
- `uv run profiles-api`: Start the FastAPI server.
- `uv run pytest`: Run the full automated test suite.
- `uv run python -c "from core.cutout_processing import get_available_turbine_list; print(get_available_turbine_list())"`: Verify turbine models.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for functions/variables, `PascalCase` for classes, and clear config names (`PROFILE_TYPE`, `LATITUDE`, etc. in `main.py`).
- Prefer explicit typing (`Path`, `pd.Series`, `dict`/`List` annotations) for public functions and models.
- Keep file and output naming patterns stable (for example: `2024_slope30_azimuth180.csv`).

If formatting/linting tools are introduced later, add them to `pyproject.toml` and document commands here.

## Testing Guidelines
- Every change must include or update tests unless it is strictly documentation-only.
- Use `pytest` and name files `tests/test_<area>.py`.
- Prefer isolated tests with `monkeypatch` for CLI/API paths so tests do not require ERA5 datasets.
- Run `uv run pytest` before handing off work.

## Documentation & Workflow Rules
- Keep `README.md` concise (quick start + pointers). Put detailed behavior, options, and examples in `/docs` and link from README.
- When behavior, commands, or interfaces change: update `/docs` first, then update README only if navigation/quick-start pointers changed.
- Do not open PRs or make commits from the agent workflow; make changes directly in this repository working tree only.
