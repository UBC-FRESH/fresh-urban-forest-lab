"""Public demo portal for the UBC and Vancouver urban-forest apps.

Run with:

    uvicorn portal_app:app --host 0.0.0.0 --port 8790

The portal mounts both demo instances under ``/ubc`` and ``/vancouver``. Each mounted app
keeps its own runtime directory, so scenarios and optimization archives do not mix.
"""

from __future__ import annotations

import os
from pathlib import Path

from fresh_urban_forest.portal import PortalDemo, create_portal_app

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime" / "portal"

app = create_portal_app(
    (
        PortalDemo(
            slug="ubc",
            label="UBC campus",
            subtitle="UBC Vancouver · campus proof",
            dataset_root=ROOT / "data" / "demo" / "ubc_core",
            runtime_dir=RUNTIME / "ubc",
            description=(
                "The original proof: 4,900 campus trees, 2021 LiDAR, 2D/3D editing, "
                "shade and species fit, growth scenarios, birds, and optimization."
            ),
            image="demo-map.png",
        ),
        PortalDemo(
            slug="vancouver",
            label="Vancouver city",
            subtitle="City of Vancouver · full city pilot",
            dataset_root=ROOT / "data" / "processed" / "vancouver_2022",
            runtime_dir=RUNTIME / "vancouver",
            description=(
                "The full-city pilot: 181 LiDAR tiles, 184k public trees, 22 local-area "
                "metrics, canopy volume, carbon, rainfall interception, shade, and a "
                "city-scale 3D scene."
            ),
            image="vancouver-city-metrics.png",
        ),
    ),
    assets_dir=ROOT / "docs" / "_static",
    allow_agent=os.environ.get("FRESH_PORTAL_ALLOW_AGENT", "").lower() in {"1", "true", "yes"},
)
