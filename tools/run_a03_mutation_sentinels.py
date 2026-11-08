"""A03/P0.2 — bounded Cloud-only mutation adequacy for read-only contracts.

NEVER edit tracked src files. Each single-token mutant is injected solely into a
fresh /tmp copy of the source package on a GitHub-hosted runner; it is restored
before the next mutant and the temporary tree is deleted afterwards.

A "killed" result means a specific independent test detects the injected bug;
the ratio is TARGETED SENTINEL adequacy, not project-wide mutation coverage.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SRC_PACKAGE = ROOT / "src" / "forex_trading"
TESTS = ROOT / "tests"
PREFIX = "test_a03_seeded_properties.A03SeededReadOnlyProperties."
ORACLE = "test_a03_mutation_oracles.A03IndependentMutationOracles."
CONTROL_TEST_COUNT = 36
SOURCE_MODULES = frozenset((
    "quotes.py", "market_data.py", "cache_core.py",
    "cache_dependency.py", "cache_indicators.py",
))


@dataclass(frozen=True)
class Mutation:
    mutation_id: str
    module: str
    original: str
    altered: str
    test: str


MUTANTS: tuple[Mutation, ...] = (
    Mutation("Q01_ENTRY_LONG_WRONG_SIDE", "quotes.py",
             "ActionIntent.ENTRY_LONG: PriceSide.ASK,",
             "ActionIntent.ENTRY_LONG: PriceSide.BID,",
             PREFIX + "test_quote_bid_ask_action_matrix_for_seeded_spreads"),
    Mutation("Q02_EXIT_SHORT_WRONG_SIDE", "quotes.py",
             "ActionIntent.EXIT_SHORT: PriceSide.ASK,",
             "ActionIntent.EXIT_SHORT: PriceSide.BID,",
             PREFIX + "test_quote_bid_ask_action_matrix_for_seeded_spreads"),
    Mutation("Q03_FIRST_KNOWN_OFF_BY_ONE", "quotes.py",
             "if quote.first_known_utc > decision_utc:",
             "if quote.first_known_utc >= decision_utc:",
             ORACLE + "test_quote_exact_first_known_boundary_is_eligible"),
    Mutation("Q04_STALE_CUTOFF_OFF_BY_ONE", "quotes.py",
             "if decision_utc - quote.first_known_utc > max_age:",
             "if decision_utc - quote.first_known_utc >= max_age:",
             PREFIX + "test_quote_known_time_boundary_is_inclusive_then_stale"),
    Mutation("Q05_UNVERIFIED_QUOTE_ACCEPTED", "quotes.py",
             "if quote.quality is not QuoteQuality.VERIFIED:",
             "if False and quote.quality is not QuoteQuality.VERIFIED:",
             PREFIX + "test_future_or_unverified_quote_never_approved_by_clock"),
    Mutation("Q06_SIDE_FORCED_ASK", "quotes.py",
             "side = _PRICE_SIDE[intent]",
             "side = PriceSide.ASK",
             PREFIX + "test_quote_bid_ask_action_matrix_for_seeded_spreads"),
    Mutation("B01_FUTURE_HTF_GATE_BYPASS", "market_data.py",
             "if htf_context_first_known_utc > bar.first_known_utc or htf_context_first_known_utc > decision_utc:",
             "if htf_context_first_known_utc > decision_utc:",
             PREFIX + "test_m5_htf_future_context_does_not_become_causal_later"),
    Mutation("B02_MID_MARKED_EXECUTABLE", "market_data.py",
             "quote_basis_ok = bar.key.side in (BarSide.BID, BarSide.ASK)",
             "quote_basis_ok = True",
             PREFIX + "test_mid_bar_remains_non_executable_even_when_technically_usable"),
    Mutation("B03_ASOF_EXCLUDES_EQUAL_TIMESTAMP", "market_data.py",
             "r.first_known_utc <= decision_utc",
             "r.first_known_utc < decision_utc",
             PREFIX + "test_asof_future_revisions_never_change_past_selection"),
    Mutation("B04_M5_ARM_GATE_SWITCHED_TO_M15", "market_data.py",
             "if bar.key.timeframe is Timeframe.M5:",
             "if bar.key.timeframe is Timeframe.M15:",
             PREFIX + "test_no_closed_bar_gate_grants_trade_authority"),
    Mutation("C01_UNBOUNDED_RANGE_ACCEPTED", "cache_core.py",
             "if not supports_bounded_range:",
             "if False:",
             PREFIX + "test_cache_no_range_is_never_rebranded_as_safe_delta"),
    Mutation("C02_DELTA_OVERLAP_TRUNCATED", "cache_core.py",
             "policy.overlap_closed_bars, len(snapshot.closed_bars)",
             "1, len(snapshot.closed_bars)",
             PREFIX + "test_incremental_cache_refresh_has_exact_bounded_overlap"),
    Mutation("C03_SAME_REVISION_CORRECTION_ACCEPTED", "cache_core.py",
             "incoming.revision_number <= old.revision_number",
             "incoming.revision_number < old.revision_number",
             ORACLE + "test_same_revision_rejected_even_if_known_later"),
    Mutation("C05_SAME_KNOWN_TIME_CORRECTION_ACCEPTED", "cache_core.py",
             "incoming.first_known_utc <= old.first_known_utc",
             "incoming.first_known_utc < old.first_known_utc",
             ORACLE + "test_higher_revision_rejected_if_not_known_later"),
    Mutation("C04_DIRTY_DEPENDENCY_DISABLED", "cache_dependency.py",
             "if any(p in affected for p in node.parents):",
             "if False:",
             PREFIX + "test_cache_dirty_dag_never_invalidates_other_pairs"),
    Mutation("E01_EMA_DEGENERATES_TO_CLOSE", "cache_indicators.py",
             "value = price if idx == 0 else alpha * price + (Decimal(1) - alpha) * out[-1]",
             "value = price",
             ORACLE + "test_ema_closed_form_weighted_three_point_oracle"),
    Mutation("E02_EMA_HALF_WEIGHT", "cache_indicators.py",
             "alpha = Decimal(2) / Decimal(period + 1)",
             "alpha = Decimal(1) / Decimal(period + 1)",
             ORACLE + "test_ema_closed_form_weighted_three_point_oracle"),
)


def replace_once(content: str, expected: str, changed: str) -> str:
    """Reject missing/ambiguous anchors and no-op mutant substitutions."""
    if not expected or not changed or expected == changed:
        raise ValueError("A03_MUTANT_EMPTY_OR_IDENTITY")
    if content.count(expected) != 1:
        raise ValueError("A03_MUTANT_ANCHOR_NOT_UNIQUE")
    result = content.replace(expected, changed, 1)
    if result == content:
        raise ValueError("A03_MUTANT_NO_CHANGE")
    return result


def validate_mutations() -> None:
    if len(MUTANTS) != 17:
        raise ValueError("A03_MUTANT_COUNT_CHANGED")
    ids = [m.mutation_id for m in MUTANTS]
    if len(ids) != len(set(ids)):
        raise ValueError("A03_MUTANT_IDS_NOT_UNIQUE")
    for mutant in MUTANTS:
        if (mutant.module not in SOURCE_MODULES or
                not re.fullmatch(r"[A-Z][0-9]{2}_[A-Z0-9_]+", mutant.mutation_id) or
                not (mutant.test.startswith(PREFIX) or
                     mutant.test.startswith(ORACLE))):
            raise ValueError("A03_MUTANT_SCOPE_VIOLATION")
        path = SRC_PACKAGE / mutant.module
        original = path.read_text(encoding="utf-8")
        altered = replace_once(original, mutant.original, mutant.altered)
        ast.parse(altered, filename=str(path))


def _run(args: list[str], env: dict[str, str], seconds: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], env=env, cwd=ROOT, shell=False,
        capture_output=True, text=True, timeout=seconds, check=False,
    )


def _mutant_result(m: Mutation, text: str, returncode: int) -> str:
    """Return KILLED/SURVIVED; infrastructure/import failures are never kills."""
    if ("Ran 1 test" not in text or "Failed to import test module" in text or
            "ModuleNotFoundError" in text or "ImportError" in text):
        return "INVALID"
    short_test = m.test.rsplit(".", 1)[-1]
    if returncode == 0:
        return "SURVIVED" if re.search(r"^OK\s*$", text, re.MULTILINE) else "INVALID"
    if (f"FAIL: {short_test} (" in text or f"ERROR: {short_test} (" in text) and (
            "FAILED (" in text):
        return "KILLED"
    return "INVALID"


def main() -> None:
    validate_mutations()
    if len(list(SRC_PACKAGE.glob("*.py"))) != 30:
        raise ValueError("A03_SOURCE_MODULE_COUNT_DRIFT")
    if not TESTS.joinpath("test_a03_seeded_properties.py").is_file() or not TESTS.joinpath(
        "test_a03_mutation_oracles.py"
    ).is_file():
        raise ValueError("A03_TEST_SOURCE_MISSING")

    # All writes are restricted to the ephemeral OS temp directory, not MFX repo.
    with tempfile.TemporaryDirectory(prefix="mfx-a03-cloud-mutants-") as tmp:
        work = Path(tmp).resolve()
        copied = work / "src" / "forex_trading"
        shutil.copytree(SRC_PACKAGE, copied, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(work / "src"), str(TESTS)))
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONNOUSERSITE"] = "1"

        probe = _run(["-c", "import forex_trading; print(forex_trading.__file__)"], env)
        if (probe.returncode != 0 or
                Path(probe.stdout.strip()).resolve() != (copied / "__init__.py").resolve()):
            raise ValueError("A03_MUTANT_IMPORT_NOT_ISOLATED")

        baseline = _run([
            "-m", "unittest", "discover", "-s", str(TESTS),
            "-p", "test_a03_*.py",
        ], env, seconds=90)
        baseline_output = baseline.stdout + baseline.stderr
        if (baseline.returncode != 0 or
                f"Ran {CONTROL_TEST_COUNT} tests" not in baseline_output or
                "OK" not in baseline_output):
            raise ValueError(
                "A03_CONTROL_SUITE_NOT_GREEN:" + baseline_output[-2800:]
            )

        results: list[dict[str, str]] = []
        for mutation in MUTANTS:
            target = copied / mutation.module
            if target.parent != copied:
                raise ValueError("A03_MUTATION_PATH_ESCAPED_TMP_SOURCE")
            original = target.read_text(encoding="utf-8")
            altered = replace_once(original, mutation.original, mutation.altered)
            ast.parse(altered, filename=str(target))
            try:
                target.write_text(altered, encoding="utf-8")
                test = _run(["-m", "unittest", "-v", mutation.test], env)
                output = test.stdout + test.stderr
                disposition = _mutant_result(mutation, output, test.returncode)
            finally:
                target.write_text(original, encoding="utf-8")
            if target.read_text(encoding="utf-8") != original:
                raise ValueError("A03_MUTATION_CLEANUP_MISMATCH")
            entry = {
                "mutation_id": mutation.mutation_id,
                "module": mutation.module,
                "target_test": mutation.test,
                "outcome": disposition,
                "mutated_sha256": hashlib.sha256(
                    altered.encode("utf-8")
                ).hexdigest(),
            }
            results.append(entry)
            if disposition == "INVALID":
                raise ValueError(
                    "A03_MUTANT_INVALID_OR_TEST_INFRA_FAILURE:" +
                    json.dumps(entry, sort_keys=True) + ":" + output[-1000:]
                )
            print("MFX_A03_MUTANT_OBSERVED " + json.dumps(entry, sort_keys=True))

    killed = sum(r["outcome"] == "KILLED" for r in results)
    survived = sum(r["outcome"] == "SURVIVED" for r in results)
    receipt = {
        "kind": "A03_P0_2_TARGETED_MUTATION_SENTINELS_ONLY",
        "sentinels": len(MUTANTS),
        "killed": killed,
        "survived": survived,
        "targeted_sentinel_mutation_score": f"{killed}/{len(MUTANTS)}",
        "baseline_control_tests": CONTROL_TEST_COUNT,
        "source_files_mutated_in_repo": 0,
        "ephemeral_runner_only": True,
        "full_project_mutation_score_measured": False,
        "genuine_tp_sl_execution_tested": False,
        "market_data_provider_called": False,
        "may_deploy_or_trade": False,
    }
    print("MFX_A03_MUTATION_SENTINEL_RECEIPT " + json.dumps(receipt, sort_keys=True))
    if killed != len(MUTANTS) or survived:
        raise SystemExit("A03_MUTATION_SENTINEL_SURVIVOR_GATE_FAILED")
    print("MFX_A03_MUTATION_SENTINELS_PASS")


if __name__ == "__main__":
    main()
