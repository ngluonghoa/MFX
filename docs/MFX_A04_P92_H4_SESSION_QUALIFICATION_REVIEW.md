# A04/P0.92 — H4 qualification review: source gaps vs unverified FX session closures

Cloud-only, non-deploying proof-of-gate (2026-11-12 UTC). **Not a market-calendar certification or permission to replace native H4.** Continue using the existing independently verified P0.91 M5 41/41 SHA / 492 fully closed bars to UTC 10:00, real H4 9 exact complete windows out of 30 minimum, <7 calendar days, native H4 8/8 SHA. No fresh market/Drive claims by this milestone.

## Why this milestone is distinct

The existing `tools/mfx_h4_source_coverage.py` (P0.70) already maps dual-source UTC four-hour gaps, distinguishing native-only, M5-only, weekend-dual-absence *candidates*, and weekday unexplained dual absence. The existing `tools/run_mfx_m5_h4_live_parity_audit.py` (P0.66) already verifies raw bounded M5/H4 SHA, OHLC equality, boundary partials and 30-window/7-day threshold. **These operational tools are not modified**.

This PR introduces a **pure offline review-only cross-field gate** in `tools/mfx_h4_qualification_gate.py`. It joins caller-provided already audited P0.66 SHA counts, latest closed-hour UTC and complete 48xM5 H4 labels with native H4 label coverage, then recomputes existing P0.70 dual-source gaps and rejects inconsistent counters/48-M5 capacity, timestamps, SHA shapes, source mismatch and any provider/write/broker activity. The 9 contiguous P0.91 labels used in offline fixtures are reconstructed from the reviewed **first 2026-11-10T20:00Z / last 2026-11-12T04:00Z** and the exact 9-grid/9 match receipt; **not** independently fetched by these tests.

### Disposition rules

| Evidence state | Offline classification | Operational result |
| --- | --- | --- |
| OHLC mismatch, M5-only/native-only H4 slot or interior incomplete 48xM5 window | P092_NO_GO_SOURCE_MISMATCH_OR_INTERIOR_GAP | No substitution |
| BOTH absent H4 slot on weekday | P092_NO_GO_UNEXPLAINED_WEEKDAY_DUAL_ABSENCE | No automatic gap waiver |
| BOTH absent UTC H4 slot on Saturday/Sunday | P092_NO_GO_UNVERIFIED_WEEKEND_SESSION_CANDIDATE | Calendar candidate only, **not proof** |
| Fewer than 30 exact complete windows or less than 7 real elapsed days | P092_NO_GO_INSUFFICIENT_30_WINDOWS_OR_7_DAYS | Continue observation |
| Synthetic sample reaches numerical threshold with no represented gaps | P092_REVIEW_THRESHOLD_ONLY_SESSION_AND_OWNER_GO_REQUIRED | Research threshold only; **still no owner GO** |

A pure classifier cannot attest its own supplied input booleans, source authenticity, provider licence, official market holiday/DST schedule or external monotonic trust witness. Therefore **every status is non-production** and its `may_replace_native_h4`, `may_reduce_native_h4_requests`, `may_change_sydney_native_d1`, `h4_production_cutover_authorized` and broker/numeric signal authority stay false. A weekend detection never waives a missing candle. An H4 calendar gap cannot be misrepresented as a continuous 48xM5 window.

`tests/test_a04_p92_h4_qualification_gate.py` adds **40 hermetic positive/negative checks**, including the real P0.91 nine-window reviewed fixture and synthetic 30/43/44-window spans, weekend/weekday source holes, bad clock/SHA/count/negative/boolean/spoofed audit receipts, and no-production/no-IO guarantees.

## Boundaries and next

- The H4 / M5 original 102 Forex source parity and numeric source strategy are unchanged. Vendor retention licence, broker BID/ASK, the 36 B2/S2 source owner approvals, live V2/CS witness, real production swaps, trading alerts/broker remain independently gated.
- No writes to private Drive, source-price API, production GitHub Actions workflows, job schedule, secret/variable, Python domain source or H4 native selector. ChatGPT hourly engineering task remains **OFF**. Existing GitHub cache writer may continue independently.
- Next P0.93: investigate externally **verifiable FX session calendar origin** and define separate reviewed calendar-evidence schema/offline tests before any waiver. A weekend heuristic does not establish an exchange/vendor calendar. Independently rerun the existing owner-approved P0.66 read-only audit when validating a new M5 head, and never imply P0.92 offline tests authenticate the latest private Drive data.
