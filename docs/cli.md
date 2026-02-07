# CLI

The CLI entrypoint is `profiles-cli`.

## Commands

```bash
uv run profiles-cli --help
uv run profiles-cli list-turbines
uv run profiles-cli list-turbines --sort name
uv run profiles-cli list-turbines --sort hub_height
uv run profiles-cli list-turbines --sort power
uv run profiles-cli list-solar-technologies
uv run profiles-cli generate --profile-type both --base-path data --output-dir output --cutout europe-2024-era5.nc
uv run profiles-cli inspect-turbine Vestas_V162_5.6
uv run profiles-cli inspect-solar-technology CSi
```

## Notes

- Use repeated `--cutout` values to run multiple weather years.
- Use repeated `--slope` and `--azimuth` values for multiple solar orientations.
- `list-turbines` supports `--sort` values: `name`, `hub_height`, `power`.
- Default sort is `power` descending; `hub_height` is descending; `name` is ascending.
- `inspect-turbine` renders a two-card view: metadata on the left and power-curve chart on the right.
- The power curve is rendered as a terminal line plot (`plotext`) with point markers, with an ASCII fallback if plotext rendering is unavailable.
- For atlite turbines, `Definition` shows `atlite/resources/windturbine/<type>` instead of an absolute path.
- For custom turbines, `Definition` shows a workspace-relative path (for example `config/wind/MyModel.yaml`).
- For custom solar technologies, `Definition` shows a workspace-relative path (for example `config/solar/MyPanel.yaml`).
- `generate` supports `--turbine-config-file` and `--solar-technology-config-file` to load local YAML definitions.
- `Source` is shown with a 40-character display label and `...` when trimmed; URL sources are clickable links in Rich-capable terminals.
- API returns the same payload at `GET /turbines/{turbine_model}`.
