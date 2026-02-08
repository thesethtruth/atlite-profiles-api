from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import xarray as xr

from core.models import CutoutDefinition, CutoutInspectResponse, CutoutPrepareConfig


def _infer_time_value(start: pd.Timestamp, end: pd.Timestamp) -> str | list[str]:
    if (
        start.year == end.year
        and start.month == 1
        and start.day == 1
        and start.hour == 0
        and end.month == 12
        and end.day == 31
        and end.hour == 23
    ):
        return f"{start.year:04d}"

    month_period = pd.Period(start, freq="M")
    month_end = month_period.end_time
    if (
        start.year == end.year
        and start.month == end.month
        and start.day == 1
        and start.hour == 0
        and end.day == month_end.day
        and end.hour == 23
    ):
        return f"{start.year:04d}-{start.month:02d}"

    return [start.isoformat(), end.isoformat()]


def _normalize_prepared_features(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return []
        if isinstance(parsed, (list, tuple)):
            return [str(item) for item in parsed]
    return []


def _step_size(values: xr.DataArray, attr_value: object) -> float | None:
    if isinstance(attr_value, (int, float)):
        return float(attr_value)
    if values.size >= 2:
        return abs(float(values[1].item()) - float(values[0].item()))
    return None


def inspect_cutout_metadata(path: Path, *, name: str) -> CutoutInspectResponse:
    with xr.open_dataset(path, chunks={}) as ds:
        x_values = ds.coords["x"]
        y_values = ds.coords["y"]
        xmin = float(x_values.min().item())
        xmax = float(x_values.max().item())
        ymin = float(y_values.min().item())
        ymax = float(y_values.max().item())
        dx = _step_size(x_values, ds.attrs.get("dx"))
        dy = _step_size(y_values, ds.attrs.get("dy"))

        time_index = ds.indexes["time"]
        time_start = pd.Timestamp(time_index[0])
        time_end = pd.Timestamp(time_index[-1])
        prepared_features = _normalize_prepared_features(
            ds.attrs.get("prepared_features")
        )

        return CutoutInspectResponse(
            filename=name,
            path=str(path),
            cutout=CutoutDefinition(
                module=str(ds.attrs.get("module", "unknown")),
                x=[xmin, xmax],
                y=[ymin, ymax],
                dx=dx,
                dy=dy,
                time=_infer_time_value(time_start, time_end),
            ),
            prepare=CutoutPrepareConfig(features=prepared_features),
            inferred=True,
        )
