# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: Entry point for local profile generation runs.
- `core/profile_generator.py`: Configuration models (`ProfileConfig`, `WindConfig`, `SolarConfig`) and orchestration logic.
- `core/cutout_processing.py`: Low-level wind/solar extraction from atlite cutouts.
- `service/cli.py`: Typer CLI commands.
- `service/api/app.py`: FastAPI application assembly and API entrypoint.
- `service/api/routers/*.py`: Feature routers for health, turbines, solar, and generation.
- `service/runner.py`: Shared execution layer used by CLI and API.
- `tests/`: `pytest` suite for CLI, API, and shared runtime behavior.
- `config/wind/*.yaml`: Local wind technology definitions loaded at runtime.
- `config/solar/*.yaml`: Local solar technology definitions loaded at runtime.
- `README.md`: Usage and setup reference.
- `pyproject.toml` and `uv.lock`: Dependency and environment lock files.

Keep domain logic in `core/`; keep `main.py` as a thin configuration and execution script.
Keep business/runtime behavior shared through `service/runner.py` so CLI and API expose the same features without duplicate implementations. The goal is that the CLI and the API service remain feature par. 

## Build, Test, and Development Commands
- `uv sync`: Create/update the virtual environment and install pinned dependencies.
- `uv run python main.py`: Run profile generation with values configured in `main.py`.
- `uv run profiles-cli --help`: Show CLI commands.
- `uv run profiles-api`: Start the FastAPI server.
- `uv run pytest`: Run the full automated test suite.
- `uv run ruff check .`: Run Ruff lint checks (same as CI).
- `uv run ruff format --check .`: Verify formatting (same as CI).
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
- For feature implementations, run CI-equivalent Ruff checks before handoff:
  - `uv run ruff check .`
  - `uv run ruff format --check .`

## Documentation & Workflow Rules
- Keep `README.md` concise (quick start + pointers). Put detailed behavior, options, and examples in `/docs` and link from README.
- When behavior, commands, or interfaces change: update `/docs` first, then update README only if navigation/quick-start pointers changed.
- Do not open PRs or make commits from the agent workflow, make changes directly in this repository working tree only.

## Engineering Reflection & Guardrails
- Pass typed data models (Pydantic/dataclasses) through the codebase. Avoid passing raw `dict` payloads between layers.
- Do not use plain `dict` payloads in application flow, including boundaries. Parse incoming payloads directly into typed models, and serialize outgoing payloads from typed models only.
- Enforce separation of concerns:
  - Core generation computes profiles only.
  - Storage concerns are explicit and isolated (separate storage config and storage handler APIs).
  - API handlers should not silently perform local file persistence unless that storage behavior is explicitly part of the API contract.
- Push back on illogical feature designs early. Example: an API that writes files locally but never exposes or returns those artifacts is a design smell and should be challenged.
- Prefer explicit, separate entrypoints for distinct responsibilities (for example compute-only vs compute-and-persist) instead of mode flags that blur behavior.
