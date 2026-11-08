#!/usr/bin/env python3
"""Apply a measured vertical-control offset to the P43/P45 change grid.

The input control estimate comes from paired 2018 class-2 ground points and the 2022 DEM.
This script reports the change metrics at the control offset and its bootstrap interval; it
does not turn the result into a field-validated or survey-grade citywide claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from fresh_urban_forest.change_sensitivity import offset_sensitivity, summarize_sensitivity


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : list of str or None
        Arguments. ``None`` uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--change-2m", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=2.0)
    parser.add_argument(
        "--p43-offset",
        type=float,
        default=1.0,
        help="Vertical offset already applied to 2022 DEM in P43",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the control-offset sensitivity and write a JSON summary.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments.

    Returns
    -------
    dict
        Control offset, interval, control-offset metrics, and P45 envelope.
    """
    control = json.loads(args.control.read_text(encoding="utf-8"))
    estimate = control["estimate"]
    offset = float(estimate["offset_m"])
    low = float(estimate["bootstrap_low_m"])
    high = float(estimate["bootstrap_high_m"])
    grid = np.load(args.change_2m / "change_grid.npz")
    earlier = grid["earlier"]
    later = grid["later"]
    valid = grid["valid"]
    change_json = json.loads((args.change_2m / "change.json").read_text(encoding="utf-8"))
    cell_area = float(change_json["metrics"].get("cell_area_m2", 4.0))
    # P43 added a +1.0 m offset to the 2022 DEM. The measured control difference is
    # 2018 ground minus 2022 DEM, so the correction to the existing earlier grid is
    # p43_offset - measured_offset.
    correction = args.p43_offset - offset
    correction_offsets = sorted(
        {args.p43_offset - high, args.p43_offset - offset, args.p43_offset - low}
    )
    control_results = offset_sensitivity(
        earlier,
        later,
        valid,
        offsets_m=correction_offsets,
        threshold_m=args.threshold,
        cell_area_m2=cell_area,
    )
    envelope_results = offset_sensitivity(
        earlier,
        later,
        valid,
        offsets_m=(-1.0, 0.0, 1.0),
        threshold_m=args.threshold,
        cell_area_m2=cell_area,
    )
    control_summary = summarize_sensitivity(control_results)
    envelope_summary = summarize_sensitivity(envelope_results)
    payload: dict[str, object] = {
        "schema_version": "fresh-urban-forest.vertical-control-sensitivity.v1",
        "control_offset_m": offset,
        "control_interval_m": [low, high],
        "p43_vertical_offset_m": args.p43_offset,
        "p43_correction_m": correction,
        "p43_correction_interval_m": [args.p43_offset - high, args.p43_offset - low],
        "control_results": [result.to_dict() for result in control_results],
        "control_summary": control_summary,
        "p45_envelope_results": [result.to_dict() for result in envelope_results],
        "p45_envelope_summary": envelope_summary,
        "decision": (
            "The measured ground-control offset is near zero in the sampled tiles, so the "
            "P43 +1.0 m assumption is not supported. Corrected to the measured ground "
            "control, the sampled screen is negative (about -95 ha), not the previous "
            "positive result. This is not a citywide probability sample and "
            "classification/co-registration/scale effects remain; do not describe it as "
            "a final citywide net loss."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "control_offset_m": offset,
        "control_interval_m": [low, high],
        "control_net_m2": {
            str(result.offset_m): round(result.metrics.net_m2, 1) for result in control_results
        },
        "out": str(args.out),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the control-offset sensitivity.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments.

    Returns
    -------
    int
        Zero on success.
    """
    args = parse_args(argv)
    print(json.dumps(run(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
