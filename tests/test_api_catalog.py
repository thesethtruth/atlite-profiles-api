from service.api.catalog import load_catalog_snapshot


def test_load_catalog_snapshot_discovers_cutouts_from_sources(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "a.nc").write_text("x", encoding="utf-8")
    (data_dir / "b.txt").write_text("x", encoding="utf-8")

    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "c.nc").write_text("x", encoding="utf-8")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "api.yaml").write_text(
        ("cutout_sources:\n  - data\n  - nested/*.nc\n"),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "service.api.catalog.get_available_turbines",
        lambda: ["T1"],
    )
    monkeypatch.setattr(
        "service.api.catalog.get_available_solar_technologies",
        lambda: ["S1"],
    )
    monkeypatch.setattr(
        "service.api.catalog.inspect_cutout_metadata",
        lambda path, *, name: {
            "filename": name,
            "path": str(path),
            "cutout": {
                "module": "era5",
                "x": [1.0, 2.0],
                "y": [3.0, 4.0],
                "time": "2024",
            },
            "prepare": {"features": ["wind"]},
            "inferred": True,
        },
    )

    snapshot = load_catalog_snapshot()

    assert snapshot.available_turbines == ["T1"]
    assert snapshot.available_solar_technologies == ["S1"]
    assert snapshot.available_cutouts == ["a.nc", "c.nc"]
    paths = {entry.name: entry.path for entry in snapshot.cutout_entries}
    assert paths["a.nc"].endswith("/data/a.nc")
    assert paths["c.nc"].endswith("/nested/c.nc")
    assert sorted(snapshot.cutout_metadata.keys()) == ["a.nc", "c.nc"]


def test_load_catalog_snapshot_handles_missing_api_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "service.api.catalog.get_available_turbines",
        lambda: [],
    )
    monkeypatch.setattr(
        "service.api.catalog.get_available_solar_technologies",
        lambda: [],
    )
    monkeypatch.setattr(
        "service.api.catalog.inspect_cutout_metadata",
        lambda _path, *, name: {
            "filename": name,
            "path": "/tmp/missing.nc",
            "cutout": {
                "module": "era5",
                "x": [0.0, 1.0],
                "y": [0.0, 1.0],
                "time": "2024",
            },
            "prepare": {"features": []},
            "inferred": True,
        },
    )

    snapshot = load_catalog_snapshot()

    assert snapshot.available_cutouts == []
    assert snapshot.cutout_entries == []
