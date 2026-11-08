#!/usr/bin/env python3
"""Serve the verification packet and persist every label to disk."""

from __future__ import annotations

import csv
import json
import os
import threading
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SUBMISSIONS = ROOT / "submissions"
LATEST = SUBMISSIONS / "labels_latest.json"
EVENTS = SUBMISSIONS / "labels.jsonl"
LOCK = threading.Lock()


def _ensure_submissions() -> None:
    """Create the submissions directory on first use."""
    SUBMISSIONS.mkdir(exist_ok=True)


def _valid_ids() -> set[str]:
    """Return the candidate IDs in the packet template."""
    with (ROOT / "review_template.csv").open(newline="", encoding="utf-8") as handle:
        return {row["candidate_id"] for row in csv.DictReader(handle)}


def _latest() -> dict[str, object]:  # pragma: no cover - operator path
    _ensure_submissions()
    if not LATEST.exists():
        return {"labels": {}}
    return dict(json.loads(LATEST.read_text(encoding="utf-8")))


def _write_latest(labels: dict[str, object]) -> None:  # pragma: no cover - operator path
    _ensure_submissions()
    temporary = LATEST.with_suffix(".tmp")
    temporary.write_text(json.dumps({"labels": labels}, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, LATEST)


class Handler(SimpleHTTPRequestHandler):  # pragma: no cover - HTTP runtime
    """Static packet plus a tiny JSON label sink."""

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Serve labels or static packet files."""
        if urlparse(self.path).path == "/api/labels":
            self._json(200, _latest())
            return
        super().do_GET()

    def do_POST(self) -> None:
        """Persist one candidate label."""
        if urlparse(self.path).path != "/api/labels":
            self._json(404, {"detail": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 64 * 1024:
                raise ValueError("invalid body length")
            payload = json.loads(self.rfile.read(length))
            candidate_id = str(payload["candidate_id"])
            label = str(payload.get("label", ""))
            if candidate_id not in _valid_ids():
                raise ValueError("unknown candidate")
            if label not in {"", "C", "D", "U"}:
                raise ValueError("invalid label")
            row = {
                "candidate_id": candidate_id,
                "label": label,
                "notes": str(payload.get("notes", "")),
                "flags": [
                    str(flag)
                    for flag in payload.get("flags", [])
                    if isinstance(flag, str) and len(flag) <= 80
                ],
                "reviewer": str(payload.get("reviewer", "")),
                "updated": datetime.now(UTC).isoformat(),
            }
            with LOCK:
                _ensure_submissions()
                with EVENTS.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                labels = _latest().get("labels", {})
                assert isinstance(labels, dict)
                labels[candidate_id] = row
                _write_latest(labels)
            self._json(200, {"ok": True, "saved": row})
        except Exception as error:  # pragma: no cover - request guard
            self._json(400, {"detail": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        """Silence default HTTP request logging.

        Parameters
        ----------
        format : str
            Request format string.
        *args : object
            Request arguments.

        Returns
        -------
        None
            This method intentionally emits nothing.
        """
        return


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8104"))
    server = ThreadingHTTPServer(("0.0.0.0", port), partial(Handler, directory=str(ROOT)))
    print(f"review server on http://127.0.0.1:{port}/; labels -> {LATEST}")
    server.serve_forever()
