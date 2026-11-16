"""Create an image-grouped train/validation/test split for the labeling packet.

The split is by image ID, so crops from the same source image cannot leak across splits.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def run(args: argparse.Namespace) -> dict[str, object]:
    """Create and write the split.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed split arguments.

    Returns
    -------
    dict[str, object]
        Split summary.
    """
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))["samples"]
    by_image: dict[str, list[str]] = defaultdict(list)
    for sample in manifest:
        by_image[str(sample["image_id"])].append(str(sample["candidate_id"]))
    image_ids = sorted(by_image)
    random.Random(args.seed).shuffle(image_ids)
    total_images = len(image_ids)
    train_end = max(1, int(total_images * 0.70))
    validation_end = max(train_end + 1, int(total_images * 0.85))
    validation_end = min(validation_end, total_images - 1 if total_images > 2 else total_images)
    groups = {
        "train": image_ids[:train_end],
        "validation": image_ids[train_end:validation_end],
        "test": image_ids[validation_end:],
    }
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.street-tree-benchmark-split.v1",
        "phase": "P74",
        "seed": args.seed,
        "split_by": "image_id",
        "groups": {
            name: {
                "images": values,
                "image_count": len(values),
                "candidates": [
                    candidate for image_id in values for candidate in by_image[image_id]
                ],
                "candidate_count": sum(len(by_image[image_id]) for image_id in values),
            }
            for name, values in groups.items()
        },
        "note": "Labels remain in the labeling CSV; this split contains no labels.",
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed split arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=74)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the split command.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        Zero on success.
    """
    run(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
