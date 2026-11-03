"""Resumable, checksum-verified materialization of catalog sources.

A download writes to ``<name>.part`` and is renamed only after the byte count and, when
known, the SHA-256 digest match. The manifest is written after every source, so an
interrupted fetch can be resumed without re-reading the catalog. The implementation is a
deliberate, small adaptation of the FEMIC LiDAR materialization pattern.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx

from fresh_urban_forest.catalog import DatasetSource

MATERIALIZATION_SCHEMA_VERSION = "fresh-urban-forest.materialization.v1"
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class MaterializationRecord:
    """The outcome of one source download.

    Attributes
    ----------
    source_id : str
        Catalog identifier.
    url : str
        URL that was requested.
    path : str
        Repository-relative or absolute path of the completed file. Empty on failure.
    status : str
        ``pending``, ``downloading``, ``verified``, or ``failed``.
    size_bytes : int
        Number of bytes written.
    sha256 : str
        Lower-case hexadecimal digest, or an empty string.
    attempts : int
        Number of completed attempts.
    resumed_from_bytes : int
        Byte offset where a resumed transfer started.
    message : str
        Error text or a short note.
    retrieved_utc : str
        ISO timestamp.
    """

    source_id: str
    url: str
    path: str
    status: str
    size_bytes: int
    sha256: str
    attempts: int
    resumed_from_bytes: int
    message: str
    retrieved_utc: str


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 digest of a file.

    Parameters
    ----------
    path : Path
        File to hash.

    Returns
    -------
    str
        Lower-case hexadecimal digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(
    url: str,
    destination: Path,
    *,
    source_id: str = "source",
    expected_sha256: str | None = None,
    resume: bool = True,
    timeout_sec: float = 120.0,
    client: httpx.Client | None = None,
) -> MaterializationRecord:
    """Download a URL, resuming a partial file when the server supports it.

    Parameters
    ----------
    url : str
        HTTP or HTTPS URL.
    destination : Path
        Final path. A sibling ``.part`` file is used during transfer.
    source_id : str
        Catalog identifier recorded in the result.
    expected_sha256 : str or None
        Expected digest. When set, a mismatch fails the download and removes the file.
    resume : bool
        Whether to request the remaining bytes of an existing ``.part`` file.
    timeout_sec : float
        Per-request timeout in seconds.
    client : httpx.Client or None
        Optional client, used by tests to inject a mock transport.

    Returns
    -------
    MaterializationRecord
        The completed or failed download.

    Raises
    ------
    ValueError
        When ``url`` is empty.
    """
    if not url:
        raise ValueError("download url is empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    start = part.stat().st_size if resume and part.exists() else 0
    headers = {"Range": f"bytes={start}-"} if start > 0 else {}
    owned_client = client is None
    active_client = client or httpx.Client(follow_redirects=True, timeout=timeout_sec)
    attempts = 1
    try:
        with active_client.stream("GET", url, headers=headers) as response:
            if response.status_code not in {200, 206}:
                raise httpx.HTTPStatusError(
                    f"unexpected status {response.status_code}",
                    request=response.request,
                    response=response,
                )
            reset = start > 0 and response.status_code == 200
            mode = "wb" if reset or start == 0 else "ab"
            if reset:
                start = 0
            with part.open(mode) as handle:
                for chunk in response.iter_bytes(CHUNK_SIZE):
                    handle.write(chunk)
        digest = sha256_file(part)
        if expected_sha256 and digest.lower() != expected_sha256.lower():
            part.unlink(missing_ok=True)
            raise ValueError(f"sha256 mismatch for {source_id}: {digest}")
        part.replace(destination)
        return MaterializationRecord(
            source_id=source_id,
            url=url,
            path=str(destination),
            status="verified",
            size_bytes=destination.stat().st_size,
            sha256=digest,
            attempts=attempts,
            resumed_from_bytes=start,
            message="",
            retrieved_utc=_utc_now(),
        )
    except Exception as exc:
        return MaterializationRecord(
            source_id=source_id,
            url=url,
            path="",
            status="failed",
            size_bytes=part.stat().st_size if part.exists() else 0,
            sha256="",
            attempts=attempts,
            resumed_from_bytes=start,
            message=f"{type(exc).__name__}: {exc}",
            retrieved_utc=_utc_now(),
        )
    finally:
        if owned_client:
            active_client.close()


def materialize_sources(
    sources: Iterable[DatasetSource],
    destination_root: Path,
    *,
    manifest_path: Path | None = None,
    timeout_sec: float = 120.0,
    client: httpx.Client | None = None,
) -> list[MaterializationRecord]:
    """Download every direct source into a destination root.

    Parameters
    ----------
    sources : iterable of DatasetSource
        Sources to materialize. Catalog-only sources are skipped with a failed record.
    destination_root : Path
        Directory that receives the files.
    manifest_path : Path or None
        Where to write ``materialization.json``. Defaults inside the root.
    timeout_sec : float
        Per-request timeout in seconds.
    client : httpx.Client or None
        Optional injected client.

    Returns
    -------
    list of MaterializationRecord
        One record per source, in input order.
    """
    records: list[MaterializationRecord] = []
    for source in sources:
        if not source.download_url:
            records.append(
                MaterializationRecord(
                    source_id=source.source_id,
                    url=source.url,
                    path="",
                    status="failed",
                    size_bytes=0,
                    sha256="",
                    attempts=0,
                    resumed_from_bytes=0,
                    message="catalog-only source; open the landing page to choose a release",
                    retrieved_utc=_utc_now(),
                )
            )
        else:
            filename = source.filename or f"{source.source_id}.bin"
            records.append(
                download_file(
                    source.download_url,
                    destination_root / filename,
                    source_id=source.source_id,
                    timeout_sec=timeout_sec,
                    client=client,
                )
            )
            if manifest_path is not None:
                write_materialization_manifest(records, manifest_path)
    if manifest_path is not None:
        write_materialization_manifest(records, manifest_path)
    return records


def write_materialization_manifest(
    records: Iterable[MaterializationRecord],
    path: Path,
) -> Path:
    """Write a materialization manifest.

    Parameters
    ----------
    records : iterable of MaterializationRecord
        Records to persist.
    path : Path
        Destination JSON file.

    Returns
    -------
    Path
        The path that was written.
    """
    payload = {
        "schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "generated_utc": _utc_now(),
        "records": [
            {
                "source_id": record.source_id,
                "url": record.url,
                "path": record.path,
                "status": record.status,
                "size_bytes": record.size_bytes,
                "sha256": record.sha256,
                "attempts": record.attempts,
                "resumed_from_bytes": record.resumed_from_bytes,
                "message": record.message,
                "retrieved_utc": record.retrieved_utc,
            }
            for record in records
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_materialization_manifest(path: Path) -> list[Mapping[str, object]]:
    """Read the records from a materialization manifest.

    Parameters
    ----------
    path : Path
        Manifest path.

    Returns
    -------
    list of mapping
        Raw record mappings.

    Raises
    ------
    ValueError
        When the manifest does not contain a records list.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise ValueError("manifest has no records list")
    return [record for record in records if isinstance(record, Mapping)]


def _utc_now() -> str:
    """Return the current UTC time as an ISO string.

    Returns
    -------
    str
        ISO timestamp with a ``Z`` suffix.
    """
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
