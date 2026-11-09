"""A04/P0.9 CI — measured actual 7 function signatures versus 5 future schemas."""
from __future__ import annotations

import argparse
import json

from tools.a04_p09_callable_port_gaps import (
    PIN, _read_json, inspect_callable_gaps, verify_pinned,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-measure", action="store_true")
    args = parser.parse_args()
    report = inspect_callable_gaps()
    if args.bootstrap_measure:
        print("MFX_A04_P09_BOOTSTRAP_UNPINNED " + json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ))
        return
    baseline = _read_json(PIN)
    verify_pinned(report, baseline)
    print("MFX_A04_P09_PINNED_REAL_CALLABLE_GAPS_PASS")
    print("MFX_A04_P09_RECEIPT " + json.dumps({
        k: value for k, value in report.items() if k != "source_gap_rows"
    }, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
