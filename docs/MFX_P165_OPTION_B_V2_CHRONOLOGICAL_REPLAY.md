# MFX P0.165 — Option B v2 causal chronological replay of closed synthetic snapshots

Date: 2026-11-14 ICT. Scope: MFX-only signal-first engineering, using the **existing P0.161 MFX Option B independent right-confirmed B2/S2 actual numerical detector**, not a new approximation or a copy of the original Forex Trading 1.0. Never a real-source point-in-time OOS claim.

## Actual functional advancement

Before this checkpoint, P0.161 could compute one closed synthetic B2/S2 snapshot with two confirmed D1 and H4 high/low pivots and a right-confirmed M15 pre-trigger pivot. P0.159's M15 source-prefix study and older P0.33 replay did **not** apply P0.161 independent v2 policy to a sequence of B2/S2 source snapshots.

P0.165 adds `mfx_research/option_b_v2_chronological_replay.py`: an immutable, strictly increasing UTC decision-time replay of **up to 32** P0.161 source snapshots, recomputing the underlying P0.161 detector at each step; no caller-supplied actions are trusted. Source identity and M15 trigger event identity are independently hashed from the SAME synthetic source. Exact repeated event with matching full private source content and rule is explicitly suppressed; any opposite B2/S2 claim for the same trigger, same event with edited historical D1/H4/H1/M15 values or altered source stream is **rejected**, not silently overwritten. Replaying an older trigger after a newer one or supplying future-known/open/incomplete/missing M15 right bars fails closed via existing source validators. A private deterministic SHA-linked replay record can be recomputed and verified. No external exchange timestamp or provider first-known attestation is inferred from the hash.

Public record contains ONLY snapshot and de-duplication counts plus NO_SIGNAL/UNVERIFIED and false permissions. Computed private BUY/SELL experiments, simulated OHLC, pivots, per-source fingerprints and event IDs are excluded; only safe hashes stay in-memory. The P0.161 numeric profile stays unchanged: H1 zone/near/chase and D1/H4/M15 1/1 widths remain **UNAPPROVED**.

## Demonstrated bounds

Hermetic tests exercise actual B2 and S2 numeric code, two separate shifted historical decision windows, deterministic rerun, idempotent repeat, conflicting action for same trigger, same-event edited values, cross-source stream changes, naive/non-UTC/out-of-order or rollback of decision windows, future-known M15, gaps, forged policy, mutated chain, no unlicensed raw price log, and no provider/Drive/broker calls. These are **synthetic** observations, not actual historical replay, strategy profitability, real source rights, an unbiased out-of-sample dataset or a signal release.

There is **no new workflow, scheduled price request, Cache or Drive mutation, source-native D1 quarantine bypass, account/broker access, MT4/MT5, Mac/MOCHI/local job, or auto issuance of BUY/SELL**. Exactly 102 frozen Forex source Git blobs and 11 SOURCE_LOCKED Docs remain unchanged.

## Unresolved release-critical dependencies

Issue [#147](https://github.com/ngluonghoa/MFX/issues/147) real EUR/USD Sydney D1 2026-11-11 numeric price dispute remains OPEN and quarantined; Issue [#27](https://github.com/ngluonghoa/MFX/issues/27) account/tier-specific lawful Twelve Data raw and derived private Drive retention, replay and display still needs written evidence. Independent publisher first-known chronology and true historical as-of, D1 calendar/rollover, source stream coverage, owner numeric policy approval (original B2/S2 source 0/36; Option B independent v2 numerical values pending), realistic BID/ASK/fees/slippage/SL/TP/net R:R and untouched chronological OOS are not approved. MFX remains NO_SIGNAL/UNVERIFIED, no orders.

**Acceptance:** GitHub-hosted protected PR exact-head Python 3.11+3.12, frozen Forex 102/GDocs source traceability, Ruff/mypy/security, cross-python wheel, then independently verified exact protected main run. Rollback only this P0.165 replay implementation, its regression tests and documentation+SHA ledger additions; never rewrite original source Cache.
