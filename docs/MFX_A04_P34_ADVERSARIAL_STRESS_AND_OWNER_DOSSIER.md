# A04/P0.34 — Adversarial replay stress & exact 36-decision source-owner dossier

**Dated 2026-11-10 ICT.** Scope: Cloud GitHub+Google Drive, MFX-only research. This checkpoint makes **two tangible changes**: (1) executes deterministic negative/metamorphic attacks against actual P0.33 chronological SIM OHLC → P0.32 experimental B2/S2 → P0.31 22-zone research routing, and (2) provides a **fully indexed owner decision packet with all 36 missing original B2/S2 quantitative source conditions**. The user's goal is analysis and informational BUY/SELL signals, **never broker order execution**. Neither outcome here claims an executable/confirmed market signal.

## Functional stress harness — 16 reproducible cases

`mfx_research/p034_sim_adversarial_review.py` runs a two-event chronological B2 then S2 SIM replay, checks source timing and the hash-linked evidence, then performs exactly 16 predeclared mutations/attacks:

| Outcome | Scenarios | Requirement |
|---|---|---|
| **Accept only as research** | FUTURE_APPEND_PREFIX; NO_PATTERN_LAST; MUTATE_LATER_H1_VALID | Earlier prefix must be unchanged, late-only price change must alter later fixture fingerprint, no-pattern must produce no false label |
| **Reject the source before signal promotion** | DUPLICATE_ORIGIN_IDENTICAL; DUPLICATE_ORIGIN_REVISED; CLOCK_REORDER; FUTURE_GLOBAL_ASOF; OPEN_LAST_M15; PARTIAL_LAST_M15; FUTURE_KNOWN_H4; FUTURE_RETRIEVED_H1; REAL_PROVIDER_H1; REVISED_HISTORY_D1; CALENDAR_MISMATCH_H1; STREAM_MISMATCH_H1; TAMPER_CHAIN_PAYLOAD | Fail closed with expected specific reason, never publish a user alert or increment a market trade count |

The versioned receipt records a PASS only when all 16 scenarios produce the expected accept/reject outcome **and** the original replay is SIM-only, UNVERIFIED, 0 live alerts/price-provider calls/Drive real quote writes/broker orders. The harness is deterministic finite fixture stress — not a stochastic stress distribution, original Forex strategy economics, untouched real OOS, or verified vendor data. In-memory SHA256 chain is a local tamper check, not a durable signed price journal.

## Original B2/S2 — exact source owner decision matrix (36/36 outstanding)

Source locked document: [SOURCE_LOCKED_03_DETECTOR_AUDIT](https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit). Immutable verified original register `docs/MFX_A04_P21_SOURCE_PARAMETER_REGISTER.json` Git blob `ef88e20271ad93c34d9d09c0cc6148f67d321929`. Every table row has **two independent, unapproved** decisions (one B2 LONG and one S2 SHORT); paragraph indexes are zero-based source readback indices.

| # | Exact owner-specified requirement ID | Stage | B2 paragraph | S2 paragraph | Status |
|---:|---|---|---:|---:|---|
| 1 | `causal_d1_h4_trend` | R0 | 29 | 117 | Cả hai **PENDING** |
| 2 | `confirmed_pivot_left_bars` | R0 | 29 | 117 | Cả hai **PENDING** |
| 3 | `confirmed_pivot_right_bars` | R0 | 29 | 117 | Cả hai **PENDING** |
| 4 | `structural_hl_lh_invalidation` | INVALIDATION | 33 | 121 | Cả hai **PENDING** |
| 5 | `h1_zone_origin_identity` | R_C | 30 | 118 | Cả hai **PENDING** |
| 6 | `h1_zone_lookback` | R_C | 30 | 118 | Cả hai **PENDING** |
| 7 | `h1_true_range_atr_period` | R_C | 30 | 118 | Cả hai **PENDING** |
| 8 | `h1_near_zone_atr_multiple` | R_C | 30 | 118 | Cả hai **PENDING** |
| 9 | `h1_zone_width_atr_multiple` | R_C | 30 | 118 | Cả hai **PENDING** |
| 10 | `m15_early_reversal_structure` | R_E | 31 | 119 | Cả hai **PENDING** |
| 11 | `known_micro_break_confirm_rule` | R_F | 32 | 120 | Cả hai **PENDING** |
| 12 | `anti_chase_max_atr_multiple` | R_F | 37 | 125 | Cả hai **PENDING** |
| 13 | `bid_ask_spread_and_cost_gate` | R_F | 34 | 122 | Cả hai **PENDING** |
| 14 | `session_dst_rollover_news_gate` | R_F | 37 | 125 | Cả hai **PENDING** |
| 15 | `structural_sl_tp_net_r_gate` | R_F | 34 | 122 | Cả hai **PENDING** |
| 16 | `event_expiry_and_idempotence` | R_F | 9 | 9 | Cả hai **PENDING** |
| 17 | `licensed_source_first_known_revision` | R0 | 9 | 9 | Cả hai **PENDING** |
| 18 | `historical_walkforward_oos_qualification` | QA | 38 | 126 | Cả hai **PENDING** |

**Totals from source (not estimates):** 18 requirements per strategy; 36 source owner decisions **AWAITING_SOURCE_OWNER**, approved numerical values 0, evidence links 0. Exactly 14 `SIM:` research sample values exist in P0.21 and **none counts as an approved threshold**. This dossier is an *intake index*, not a workflow that can approve itself, and is deliberately SHA-sealed against revision without explicit governance. Full row-level machine-readable [decision dossier](MFX_A04_P34_SOURCE_OWNER_DECISION_DOSSIER.json).

## What is required for each authoritative approval

An external source owner must provide a dated/versioned **exact formula and units**; link to the controlling paragraph or signed supersession; specify price side, candle-close/as-of/first-known/revisions; independent positive/negative/strict-boundary fixtures; signed source compatibility review; economic requirements (spread, fees, swap, TP/SL, after-cost net-R) and valid licensed native BID/ASK plus chronological untouched OOS for appropriate parity. A `SIM:0.5_ATR` or `SIM:3_CLOSED_H1_BARS` research example is explicitly not such an approval. An owner can also **REJECT** or **DEFER** any item, but cannot be silently forced to approve to fit the experimental model. No credentials or contracts should be posted in the public repo.

### Explicit project hard stops

- **MFX effective design taxonomy stays 22 labels** = 8 BUY entry candidates + 8 SELL entry candidates + 2 WATCH + 4 protective, 11 conceptual mirror families. Only B2/S2 have experimental computed SIM OHLC pilots, **not** official 1:1 source predicates, and P0.34 does **not** build new detectors for the other 20 zones.
- All output action `NO_SIGNAL`, `source_approved_numeric_entry_rules=0`, `confirmed_real_signals=0`, `real_market_data_calls=0`, `real_drive_quote_writes=0`, `alerts_published=0`, `broker_orders=0`, `release_ready=false`. Never submit real orders under MFX's signal-only product scope.
- Original Forex Trading 1.0 18-zone source and source-locked Docs are untouched. Historical P0.28E MFX 19-zone checkpoint and current P0.30 22-zone design remain separate. These 36 source quantitative blockers are tracked in [Issue #45](https://github.com/ngluonghoa/MFX/issues/45), data/retention rights in [Issue #27](https://github.com/ngluonghoa/MFX/issues/27).
- [P0.34 Issue #60](https://github.com/ngluonghoa/MFX/issues/60) preregistered 24 methods before coding; hosted GitHub Actions full Python3.11/3.12 inherited unittests plus new tests, Ruff/mypy strict, frozen source golden, wheel parity. Protected squash and separate independent `main` event=push CI evidence are both required for final QA; if latter is unavailable, issue stays OPEN/PENDING.

Next genuine external decision: authorized source owner signs or explicitly rejects/defers each of the 36 clauses, plus legal terms for real FX quote access and Drive retention. This can occur independently of further synthetic harness tests.
