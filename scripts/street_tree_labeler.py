"""Serve the local street-tree labeling packet and persist labels.

The server is an operator tool. It serves only the packet manifest, its crop directory, and
the local label CSV; it does not call external services.
"""

from __future__ import annotations

import argparse
import csv
import json
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

LABEL_FIELDS = ("tree_present", "trunk_visible", "box_quality", "notes")
TREE_VALUES = {"", "yes", "partial", "no"}
TRUNK_VALUES = {"", "yes", "no"}
QUALITY_VALUES = {"", "good", "loose", "bad"}


class LabelStore:
    """Thread-safe CSV label store."""

    def __init__(self, path: Path, manifest: list[dict[str, Any]]) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.rows = self._load(manifest)

    def _load(self, manifest: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
        rows: dict[str, dict[str, str]] = {}
        if self.path.is_file():
            with self.path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    candidate_id = str(row.get("candidate_id", ""))
                    if candidate_id:
                        rows[candidate_id] = {
                            field: str(row.get(field, "")) for field in LABEL_FIELDS
                        }
        for item in manifest:
            candidate_id = str(item["candidate_id"])
            rows.setdefault(candidate_id, dict.fromkeys(LABEL_FIELDS, ""))
        return rows

    def all(self) -> dict[str, dict[str, str]]:
        """Return a copy of all labels."""
        with self.lock:
            return {key: dict(value) for key, value in self.rows.items()}

    def update(self, candidate_id: str, payload: dict[str, object]) -> dict[str, str]:
        """Validate and persist one label row."""
        with self.lock:
            if candidate_id not in self.rows:
                raise KeyError(candidate_id)
            values = {field: str(payload.get(field, "")) for field in LABEL_FIELDS}
            if values["tree_present"] not in TREE_VALUES:
                raise ValueError("invalid tree_present")
            if values["trunk_visible"] not in TRUNK_VALUES:
                raise ValueError("invalid trunk_visible")
            if values["box_quality"] not in QUALITY_VALUES:
                raise ValueError("invalid box_quality")
            values["notes"] = values["notes"][:500]
            self.rows[candidate_id] = values
            self._write()
            return dict(values)

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["candidate_id", *LABEL_FIELDS])
            writer.writeheader()
            for candidate_id, values in self.rows.items():
                writer.writerow({"candidate_id": candidate_id, **values})
        temporary.replace(self.path)


def _validated_labels(payload: object) -> tuple[str, dict[str, object]]:
    if not isinstance(payload, dict):
        raise ValueError("expected an object")
    candidate_id = payload.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("missing candidate_id")
    return candidate_id, payload


class LabelHandler(SimpleHTTPRequestHandler):
    """HTTP handler with manifest, label, and crop routes."""

    server_version = "StreetTreeLabeler/1.0"

    def __init__(
        self,
        *args: object,
        packet_dir: Path,
        manifest: list[dict[str, Any]],
        store: LabelStore,
        static_dir: Path,
        **kwargs: object,
    ) -> None:
        self.packet_dir = packet_dir
        self.manifest = manifest
        self.store = store
        self.static_dir = static_dir
        super().__init__(*args, directory=str(static_dir), **kwargs)  # type: ignore[arg-type]

    def log_message(self, format: str, *args: object) -> None:
        """Keep the operator console quiet."""
        return

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Serve the manifest, labels, crops, and static UI."""
        parsed = urlparse(self.path)
        if parsed.path == "/api/manifest":
            samples = []
            for item in self.manifest:
                crop = Path(str(item.get("crop", ""))).name
                samples.append({**item, "crop": crop})
            self._json({"samples": samples})
            return
        if parsed.path == "/api/labels":
            self._json({"labels": self.store.all()})
            return
        if parsed.path.startswith("/crops/"):
            name = Path(parsed.path.removeprefix("/crops/")).name
            path = self.packet_dir / "crops" / name
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self) -> None:
        """Persist one validated label row."""
        if urlparse(self.path).path != "/api/labels":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            candidate_id, values = _validated_labels(payload)
            saved = self.store.update(candidate_id, values)
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self._json({"candidate_id": candidate_id, "labels": saved})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed server arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the labeling server.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        Zero after the server stops.
    """
    args = parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))["samples"]
    store = LabelStore(args.labels, manifest)
    static_dir = Path(__file__).resolve().parents[1] / "tools" / "street_tree_labeler"
    handler = lambda *handler_args, **handler_kwargs: LabelHandler(  # noqa: E731
        *handler_args,
        packet_dir=args.packet_dir,
        manifest=manifest,
        store=store,
        static_dir=static_dir,
        **handler_kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Labeling UI: http://{args.host}:{args.port}/", flush=True)
    print(f"Labels: {args.labels}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
