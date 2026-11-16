# P70 v0.8.0 street-tree audit release

Status: complete. Release PR #331 merged as `a4457d7`; tag `v0.8.0` and GitHub release published.

## Verification

- `python scripts/dashboard.py`: **GREEN**
- `pytest`: **640 passed**
- Ruff, format, mypy, and workflow checks: pass
- Release metadata test: pass
- Vancouver canonical layer: **19,790** candidates
- Vancouver public-tree matches within 8 m: **6,078**
- Public portal routes `/`, `/ubc/`, `/vancouver/`, `/surrey/`, `/burnaby/`, and
  `/coquitlam/`: HTTP 200
- Playwright Vancouver smoke: `street trees · 19,790`, no console/page errors

## Release actions

- Release PR #331 squash-merged as `a4457d7`.
- Tag `v0.8.0` points at `a4457d7`.
- GitHub release `v0.8.0` published.
- Public portal verified after the release.

## Limits

No canonical data replacement, new detector, field validation, precision/recall, ownership,
survival, or complete-census claim. The P69 multi-view subset remains external and sample-only.
