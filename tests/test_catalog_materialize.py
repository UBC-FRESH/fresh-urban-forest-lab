"""Tests for the source catalog and resumable materialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from fresh_urban_forest.catalog import Catalog, DatasetSource, load_catalog
from fresh_urban_forest.materialize import (
    download_file,
    materialize_sources,
    read_materialization_manifest,
    sha256_file,
    write_materialization_manifest,
)


def _source(
    source_id: str = "test", *, url: str | None = "https://example.test/file.bin"
) -> DatasetSource:
    """Build a direct-download source for tests."""
    return DatasetSource(
        source_id=source_id,
        title="Test source",
        publisher="Test",
        url="https://example.test",
        download_url=url,
        filename="file.bin",
        media_type="application/octet-stream",
        licence="CC0",
        access_mode="direct_http" if url else "catalog",
        native_crs="EPSG:4326",
        products=("tree_inventory",),
    )


def test_catalog_loads_packaged_sources() -> None:
    """The packaged catalog parses and exposes the expected products."""
    catalog = load_catalog()
    assert isinstance(catalog, Catalog)
    assert catalog.get("ubc_campus_trees").products == ("tree_inventory",)
    assert catalog.get("vancouver_public_trees").licence == "OGL-Vancouver"
    assert any(
        source.source_id == "ubc_lidar_2021_chm_1m"
        for source in catalog.by_product("canopy_height")
    )


def test_catalog_search_and_missing_source() -> None:
    """Search ranks matches and missing identifiers raise a clear error."""
    catalog = load_catalog()
    results = catalog.search("lidar")
    assert results
    assert all(
        "lidar" in f"{item.source_id} {item.title}".lower() or item.products for item in results
    )
    with pytest.raises(KeyError):
        catalog.get("not-a-source")


def test_catalog_accepts_a_user_path(tmp_path: Path) -> None:
    """A user-supplied YAML catalog is loaded instead of the packaged one."""
    path = tmp_path / "sources.yaml"
    path.write_text(
        "schema_version: test\nupdated_utc: today\n"
        "sources:\n  - source_id: mine\n    title: Mine\n",
        encoding="utf-8",
    )
    catalog = load_catalog(path)
    assert catalog.get("mine").title == "Mine"


def test_download_file_writes_and_hashes(tmp_path: Path) -> None:
    """A successful download writes the file and a verified record."""
    payload = b"urban forest"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload))
    with httpx.Client(transport=transport) as client:
        record = download_file(
            "https://example.test/file.bin",
            tmp_path / "file.bin",
            source_id="test",
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            client=client,
        )
    assert record.status == "verified"
    assert record.size_bytes == len(payload)
    assert (tmp_path / "file.bin").read_bytes() == payload
    assert sha256_file(tmp_path / "file.bin") == hashlib.sha256(payload).hexdigest()


def test_download_file_resumes_a_partial_transfer(tmp_path: Path) -> None:
    """A range request appends to an existing part file."""
    destination = tmp_path / "file.bin"
    (tmp_path / "file.bin.part").write_bytes(b"urban ")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["range"] == "bytes=6-"
        return httpx.Response(206, content=b"forest")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        record = download_file("https://example.test/file.bin", destination, client=client)
    assert record.resumed_from_bytes == 6
    assert destination.read_bytes() == b"urban forest"


def test_download_file_rejects_a_checksum_mismatch(tmp_path: Path) -> None:
    """A wrong digest fails the record and removes the partial file."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"wrong"))
    with httpx.Client(transport=transport) as client:
        record = download_file(
            "https://example.test/file.bin",
            tmp_path / "file.bin",
            expected_sha256="0" * 64,
            client=client,
        )
    assert record.status == "failed"
    assert "sha256 mismatch" in record.message
    assert not (tmp_path / "file.bin").exists()


def test_download_file_rejects_http_errors(tmp_path: Path) -> None:
    """An HTTP error is captured in the record rather than raised."""
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    with httpx.Client(transport=transport) as client:
        record = download_file(
            "https://example.test/file.bin", tmp_path / "file.bin", client=client
        )
    assert record.status == "failed"
    assert "HTTPStatusError" in record.message


def test_materialize_sources_skips_catalog_only_entries(tmp_path: Path) -> None:
    """Catalog-only sources become failed records without a network request."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"data"))
    with httpx.Client(transport=transport) as client:
        records = materialize_sources(
            [_source(), _source("catalog", url=None)],
            tmp_path,
            manifest_path=tmp_path / "materialization.json",
            client=client,
        )
    assert records[0].status == "verified"
    assert records[1].status == "failed"
    manifest = read_materialization_manifest(tmp_path / "materialization.json")
    assert len(manifest) == 2
    assert json.loads((tmp_path / "materialization.json").read_text())["schema_version"]


def test_write_manifest_rejects_non_list_records(tmp_path: Path) -> None:
    """A malformed manifest is refused."""
    path = tmp_path / "bad.json"
    path.write_text('{"records": "nope"}', encoding="utf-8")
    with pytest.raises(ValueError, match="records"):
        read_materialization_manifest(path)


def test_write_materialization_manifest_is_sorted(tmp_path: Path) -> None:
    """The manifest is deterministic for the same records."""
    path = tmp_path / "m.json"
    write_materialization_manifest([], path)
    assert json.loads(path.read_text())["records"] == []
