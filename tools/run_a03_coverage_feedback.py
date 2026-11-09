"""A03/P0.5b: bounded deterministic *observed arc-feedback* synthetic fuzz.

Runs only on GitHub-hosted CI with coverage.py 7.10.7. Each candidate is
executed under a new branch-instrumented coverage collector. Input mutation
expands ONLY from cases that reveal previously unseen measured execution arcs.
This is a genuinely feedback-directed, grammar-bounded OANDA-shaped parser
probe, NOT full-system fuzz, licensed data, credentials, a trade or OOS testing.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import coverage

from forex_trading.cache_core import CachePartition
from forex_trading.market_data import BarSide, Timeframe
from forex_trading import provider_delta_contract as provider

ORIGIN = datetime(2026, 11, 7, 10, tzinfo=timezone.utc)
CUTOFF = ORIGIN + timedelta(minutes=15)
OBSERVED = ORIGIN + timedelta(minutes=16)
MAX_CASES = 80
MAX_DEPTH = 2
MUTATIONS = (
    "wrong_instrument", "wrong_granularity", "candles_not_list",
    "empty_page", "row_not_mapping", "time_not_string",
    "time_invalid_format", "time_nanoseconds", "time_before_window",
    "time_at_cutoff", "complete_not_bool", "provisional_row",
    "volume_boolean", "volume_negative", "bid_missing", "ask_missing",
    "bid_price_zero", "ask_price_nonstr", "bid_high_below_open",
    "duplicate_rows", "unsorted_rows",
)


def _request() -> provider.SyntheticOandaRequest:
    partition = CachePartition(
        "SYNTHETIC-FEEDBACK-ONLY", "NO-REAL-PRODUCT",
        "EURUSD-SYNTHETIC", BarSide.BID, Timeframe.M5,
        "SYNTHETIC-CALENDAR", "SYNTHETIC-AGG",
        "UTC-ONLY", "NO-VENDOR-ENTITLEMENT", "TEST-SCHEMA",
    )
    return provider.SyntheticOandaRequest(
        partition, "EUR_USD", ORIGIN, CUTOFF
    )


def _base_payload() -> dict[str, Any]:
    return {
        "instrument": "EUR_USD",
        "granularity": "M5",
        "candles": [{
            "time": "2026-11-07T10:00:00.000000000Z",
            "complete": True, "volume": 3,
            "bid": {"o": "1.10000", "h": "1.11000",
                    "l": "1.09000", "c": "1.10000"},
            "ask": {"o": "1.10020", "h": "1.11020",
                    "l": "1.09020", "c": "1.10020"},
        }],
    }


def _mutate(payload: dict[str, Any], mutation: str) -> dict[str, Any] | None:
    """Deterministically mutate one typed JSON fixture dimension."""
    if mutation not in MUTATIONS:
        raise ValueError("P05_UNKNOWN_MUTATION")
    candidate = deepcopy(payload)
    if mutation == "wrong_instrument":
        candidate["instrument"] = "GBP_USD"
    elif mutation == "wrong_granularity":
        candidate["granularity"] = "H4"
    elif mutation == "candles_not_list":
        candidate["candles"] = "not-a-list"
    elif mutation == "empty_page":
        candidate["candles"] = []
    else:
        rows = candidate.get("candles")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        row = rows[0]
        if mutation == "row_not_mapping":
            candidate["candles"] = ["not-a-record"]
        elif mutation == "time_not_string":
            row["time"] = 123
        elif mutation == "time_invalid_format":
            row["time"] = "2026-11-07T10:00:00+07:00"
        elif mutation == "time_nanoseconds":
            row["time"] = "2026-11-07T10:00:00.123456789Z"
        elif mutation == "time_before_window":
            row["time"] = "2026-11-07T09:55:00Z"
        elif mutation == "time_at_cutoff":
            row["time"] = "2026-11-07T10:15:00Z"
        elif mutation == "complete_not_bool":
            row["complete"] = 1
        elif mutation == "provisional_row":
            row["complete"] = False
        elif mutation == "volume_boolean":
            row["volume"] = False
        elif mutation == "volume_negative":
            row["volume"] = -1
        elif mutation in ("bid_missing", "ask_missing"):
            row.pop("bid" if mutation == "bid_missing" else "ask", None)
        elif mutation == "bid_price_zero":
            if not isinstance(row.get("bid"), dict):
                return None
            row["bid"]["o"] = "0"
        elif mutation == "ask_price_nonstr":
            if not isinstance(row.get("ask"), dict):
                return None
            row["ask"]["o"] = 1.10020
        elif mutation == "bid_high_below_open":
            if not isinstance(row.get("bid"), dict):
                return None
            row["bid"]["h"] = "1.00000"
        elif mutation == "duplicate_rows":
            candidate["candles"] = [deepcopy(row), deepcopy(row)]
        elif mutation == "unsorted_rows":
            newer = deepcopy(row)
            newer["time"] = "2026-11-07T10:05:00Z"
            older = deepcopy(row)
            older["time"] = "2026-11-07T10:00:00Z"
            candidate["candles"] = [newer, older]
    return candidate


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"))


def _execute_instrumented(
    payload: dict[str, Any], source_path: str, request: provider.SyntheticOandaRequest,
) -> tuple[set[tuple[int, int]], str]:
    """One fresh collector: no cross-candidate inherited arcs or disk files."""
    collector = coverage.Coverage(
        branch=True, include=[source_path], data_file=None,
    )
    collector.start()
    try:
        try:
            result = provider.parse_synthetic_oanda_candles(
                payload, request, OBSERVED, max_rows=8,
            )
            outcome = "STAGED:" + str(len(result.pairs)) + ":" + str(
                result.open_candle_count_skipped
            )
            if result.may_commit_real_cache or result.vendor_response_verified:
                raise RuntimeError("P05_UNAUTHORIZED_PROVIDER_PROMOTION")
        except (ValueError, TypeError) as exc:
            outcome = type(exc).__name__ + ":" + str(exc)
    finally:
        collector.stop()
    data = collector.get_data()
    arcs = data.arcs(source_path)
    if not arcs:
        raise ValueError("P05_NO_REAL_EXECUTION_ARCS")
    return {tuple(arc) for arc in arcs}, outcome


def explore() -> dict[str, Any]:
    """Novel observed arcs decide whether mutated children are explored."""
    source_path = str(Path(provider.__file__).resolve())
    if not source_path.endswith("/forex_trading/provider_delta_contract.py"):
        raise ValueError("P05_UNEXPECTED_SOURCE_MODULE")
    request = _request()
    queue: deque[tuple[dict[str, Any], int, str]] = deque([
        (_base_payload(), 0, "seed"),
    ])
    seen: set[str] = set()
    union: set[tuple[int, int]] = set()
    corpus: list[dict[str, Any]] = []
    rejected_expected = 0
    while queue and len(seen) < MAX_CASES:
        payload, depth, mutation = queue.popleft()
        key = _canonical(payload)
        if key in seen:
            continue
        seen.add(key)
        arcs, outcome = _execute_instrumented(payload, source_path, request)
        new = arcs - union
        if outcome.startswith(("ValueError:", "TypeError:")):
            rejected_expected += 1
        if not new:
            continue  # no novel observed execution arcs: NO further mutation
        union.update(new)
        corpus.append({
            "input_sha256": sha256(key.encode("utf-8")).hexdigest(),
            "mutation": mutation, "depth": depth, "new_arcs": len(new),
            "outcome": outcome,
        })
        if depth < MAX_DEPTH:
            for operation in MUTATIONS:
                next_payload = _mutate(payload, operation)
                if next_payload is not None and _canonical(next_payload) not in seen:
                    queue.append((next_payload, depth + 1, operation))

    if (len(seen) < 10 or len(corpus) < 5 or len(union) < 20 or
            rejected_expected < 5 or len(seen) > MAX_CASES):
        raise ValueError("P05_FEEDBACK_BUDGET_OR_NOVELTY_NOT_MET")
    digest = sha256(json.dumps(corpus, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "kind": "A03_P0_5B_OBSERVED_ARC_FEEDBACK_SYNTHETIC_PARSER_ONLY",
        "coverage_version": coverage.__version__,
        "source": "src/forex_trading/provider_delta_contract.py",
        "cases_executed": len(seen),
        "max_cases": MAX_CASES,
        "max_mutation_depth": MAX_DEPTH,
        "candidate_mutators": len(MUTATIONS),
        "coverage_interesting_corpus_size": len(corpus),
        "observed_execution_arcs_union": len(union),
        "expected_rejected_cases": rejected_expected,
        "corpus_sha256": digest,
        "feedback_controls_next_mutations": True,
        "per_input_shrinking_implemented": False,
        "whole_program_coverage_guided_fuzz": False,
        "real_provider_called": False,
        "may_persist_real_data": False,
        "may_deploy_or_trade": False,
    }


def main() -> None:
    print("MFX_P05B_ARC_FEEDBACK_RECEIPT " + json.dumps(
        explore(), sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
