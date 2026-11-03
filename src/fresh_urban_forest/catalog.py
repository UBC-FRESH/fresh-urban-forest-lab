"""A small, explicit catalog of public urban-forest data sources.

The catalog is a YAML resource so a contributor can add a source without touching Python.
It records the licence, the native CRS, the products a source can supply, and whether the
URL is a direct download or a landing page that needs a human decision.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class DatasetSource:
    """One catalog entry.

    Attributes
    ----------
    source_id : str
        Stable identifier used by the CLI, the manifest, and the dataset builder.
    title : str
        Human-readable title.
    publisher : str
        Organisation that publishes the source.
    url : str
        Landing page or canonical record.
    download_url : str or None
        Direct download URL when one exists.
    filename : str or None
        Suggested local filename.
    media_type : str
        MIME type of the payload.
    licence : str
        Licence identifier or short statement.
    access_mode : str
        ``direct_http``, ``catalog``, or ``manual``.
    native_crs : str
        Native coordinate reference system.
    products : tuple of str
        Product names such as ``tree_inventory`` or ``canopy_height``.
    notes : str
        Caveats and attribution notes.
    """

    source_id: str
    title: str
    publisher: str
    url: str
    download_url: str | None
    filename: str | None
    media_type: str
    licence: str
    access_mode: str
    native_crs: str
    products: tuple[str, ...]
    notes: str = ""

    @property
    def is_direct(self) -> bool:
        """Return whether the source has a direct download URL.

        Returns
        -------
        bool
            ``True`` when :attr:`download_url` is set.
        """
        return bool(self.download_url)


@dataclass(frozen=True, slots=True)
class Catalog:
    """An ordered collection of data sources.

    Attributes
    ----------
    schema_version : str
        Catalog schema identifier.
    updated_utc : str
        ISO date of the last catalog edit.
    sources : tuple of DatasetSource
        Sources in catalog order.
    """

    schema_version: str
    updated_utc: str
    sources: tuple[DatasetSource, ...]

    def get(self, source_id: str) -> DatasetSource:
        """Return one source by identifier.

        Parameters
        ----------
        source_id : str
            Catalog identifier.

        Returns
        -------
        DatasetSource
            The matching source.

        Raises
        ------
        KeyError
            When the identifier is not in the catalog.
        """
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise KeyError(f"unknown source: {source_id}")

    def search(self, query: str, *, limit: int = 10) -> list[DatasetSource]:
        """Rank sources by a case-insensitive substring or fuzzy match.

        Parameters
        ----------
        query : str
            Search text.
        limit : int
            Maximum number of results.

        Returns
        -------
        list of DatasetSource
            The best matches, highest score first.
        """
        text = query.strip().lower()
        if not text:
            return list(self.sources[:limit])
        scored: list[tuple[float, DatasetSource]] = []
        for source in self.sources:
            haystack = (
                f"{source.source_id} {source.title} {source.publisher} {source.products}".lower()
            )
            if text in haystack:
                score = 100.0 + len(text) / max(len(haystack), 1)
            else:
                score = difflib.SequenceMatcher(None, text, haystack).ratio()
            if score >= 0.25:
                scored.append((score, source))
        scored.sort(key=lambda item: (-item[0], item[1].source_id))
        return [source for _, source in scored[:limit]]

    def by_product(self, product: str) -> list[DatasetSource]:
        """Return sources that advertise a product.

        Parameters
        ----------
        product : str
            Product name, such as ``tree_inventory``.

        Returns
        -------
        list of DatasetSource
            Matching sources in catalog order.
        """
        return [source for source in self.sources if product in source.products]


def load_catalog(path: Path | None = None) -> Catalog:
    """Load the packaged catalog or a user-supplied YAML file.

    Parameters
    ----------
    path : Path or None
        Optional catalog path. ``None`` loads the packaged resource.

    Returns
    -------
    Catalog
        The parsed catalog.

    Raises
    ------
    ValueError
        When the YAML does not contain a ``sources`` list.
    """
    if path is None:
        text = (
            resources.files("fresh_urban_forest.resources")
            .joinpath("sources.yaml")
            .read_text(encoding="utf-8")
        )
        raw = yaml.safe_load(text)
    else:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or not isinstance(raw.get("sources"), list):
        raise ValueError("catalog must contain a sources list")
    sources = tuple(_source_from_mapping(item) for item in raw["sources"])
    return Catalog(
        schema_version=str(raw.get("schema_version", "fresh-urban-forest.sources.v1")),
        updated_utc=str(raw.get("updated_utc", "")),
        sources=sources,
    )


def _source_from_mapping(item: object) -> DatasetSource:
    """Build a source from one YAML mapping.

    Parameters
    ----------
    item : object
        One item from the ``sources`` list.

    Returns
    -------
    DatasetSource
        The parsed source.

    Raises
    ------
    ValueError
        When the item is not a mapping or lacks a source identifier.
    """
    if not isinstance(item, Mapping):
        raise ValueError("each source must be a mapping")
    source_id = str(item.get("source_id", "")).strip()
    if not source_id:
        raise ValueError("each source needs a source_id")
    products = item.get("products", [])
    return DatasetSource(
        source_id=source_id,
        title=str(item.get("title", source_id)),
        publisher=str(item.get("publisher", "unknown")),
        url=str(item.get("url", "")),
        download_url=_optional_text(item.get("download_url")),
        filename=_optional_text(item.get("filename")),
        media_type=str(item.get("media_type", "application/octet-stream")),
        licence=str(item.get("licence", "unknown")),
        access_mode=str(item.get("access_mode", "catalog")),
        native_crs=str(item.get("native_crs", "EPSG:4326")),
        products=tuple(str(product) for product in products) if isinstance(products, list) else (),
        notes=str(item.get("notes", "")).strip(),
    )


def _optional_text(value: object) -> str | None:
    """Return a stripped string or ``None``.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    str or None
        The stripped string, or ``None`` when empty.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None
