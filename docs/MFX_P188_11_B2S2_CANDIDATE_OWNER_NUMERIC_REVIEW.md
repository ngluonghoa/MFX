# MFX P0.188 — 11 MFX-only B2/S2 numeric candidates for genuine source-owner review

**Date:** 2026-11-17 ICT. **Goal:** Sunday 2026-11-22 *conditional* B2 BUY / S2 SELL informational MVP. **Scope:** original 102 frozen Forex Git blobs and 11 SOURCE_LOCKED Docs stay untouched. No provider, Drive quote, cron, OAuth, broker or production signal changes.

## Why this PR exists

[P0.187](https://github.com/ngluonghoa/MFX/pull/187) already composes the real *read-only software path* from caller-provided SHA-audited M5/H4/D1 sealed archive through six closed frames M5/M15/M30/H1/H4/D1, then source-pinned 18 paired B2/S2 proposal intake, and returns `NO_SIGNAL`. The immediate release blocker is **no owner-approved numerical strategy**. The existing P0.184 public-safe template has 18 **blank** source requirement pairs, and original Forex `SOURCE_LOCKED_03` has `SPEC_PENDING` numerical source rules (0/36 original-source approvals).

There are nevertheless two previously accepted **MFX-owned experimental** settings:

- [P160 numeric draft](MFX_V1_B2S2_INDEPENDENT_POLICY_DRAFT.json), pinned Git blob `dbaed8ca436904fd83c528818358e677def43be3`: H1 3-bar simple **mean true range**, H1 3-bar zone lookback, zone width `0.3 × mean TR`, near-zone `0.5 × mean TR`, maximum chase `0.5 × mean TR`.
- [P161 confirmed pivots draft](MFX_V1_B2S2_CONFIRMED_SWING_DRAFT_V2.json), pinned Git blob `3e172f48458ccf953f2fba2e31dde7572059e00f`: D1/H4 and M15 1-left/1-right confirmed swing windows; two observed highs/lows are required for an uptrend/downtrend proposal, all source M15 pivot confirmation must precede the trigger bar. **These are synthetic research parameters**, not official Forex numeric 1:1 or licensed real-data source rules.

P188 maps 11 of the 18 source-anchored requirements to these candidate methods with **two explicit directional formulas** for B2/S2, source paragraph/phase unchanged. The seven remaining requirements are reported `UNRESOLVED_OWNER_OR_EXTERNAL_EVIDENCE`, never invented.

| Original requirement | MFX experimental candidate for owner to accept/reject/supersede |
|---|---|
| D1/H4 trend | 1L/1R confirmed D1+H4 swing highs/lows; both higher for B2, both lower for S2 |
| Pivot left / right | 1 closed left and 1 closed right confirmation for both HTFs and M15 |
| H1 zone origin | B2 minimum of last 3 H1 lows; S2 maximum of last 3 H1 highs |
| H1 lookback | 3 fully closed H1 bars |
| H1 ATR-period | 3-bar **simple mean TRUE RANGE**, explicitly **not Wilder ATR** (methodological deviation needs owner decision) |
| Near-zone | Prior closed M15 overlaps expanded support/resistance by 0.5 × H1 mean TR |
| Zone width | B2 support [anchor, anchor+0.3 × mean TR]; S2 resistance [anchor−0.3 × mean TR, anchor] |
| Early M15 reversal | Prior closed M15 near zone and micro pivot 1L/1R confirmed before the trigger |
| Micro break | B2 close crosses above previously known micro high; S2 closes below micro low |
| Anti-chase | Price travel no more than 0.5 × H1 mean TR beyond known micro level |

These are **11 paired review suggestions = up to 22 side-specific nonapproved proposals**, NOT any of the 36 original approved formulas. No automatic mirroring from a B2-only source: both directional expressions are present for the human reviewer. The method differences (mean TR vs ATR and low/high pivot confirmation) must be explicitly decided.

**Seven still unresolved, with no made-up numerical values:** `structural_hl_lh_invalidation`, `bid_ask_spread_and_cost_gate`, `session_dst_rollover_news_gate`, `structural_sl_tp_net_r_gate`, `event_expiry_and_idempotence`, `licensed_source_first_known_revision`, `historical_walkforward_oos_qualification`.

## Operator / reviewer action

1. Examine the proposed B2 and S2 expressions separately, compare with the exact paragraph of `SOURCE_LOCKED_03`, and mark each for independent source-owner **accept, amend, reject or defer**. If the MFX methodology differs from old Forex, record an **explicit policy supersession decision**. User approval of the **deadline or mirror design is not numeric approval**.
2. A reviewer may provide a genuine externally retained **SHA-256 digest** of a non-secret owner evidence document and select 1–11 of the proposed original requirements. Only then call `prepare_p184_external_review(externally_supplied_evidence_sha256=..., selected_requirement_ids=(...))`, which validates and produces an exact `P184` two-sided **PROPOSE_FORMULA** intake packet. SHA format is checked, not the external identity/document or source license; the digest **is not a signature**. Do not pass fabricated hashes in real operation.
3. P184 delegates to P035 and still returns **0/36 owner-approved**, `NO_SIGNAL`, no quote-side or broker. A future independent signed owner process must authenticate and sign **both** side-specific formulas, reconcile all 36 original requirements, source rights and actual MID/BIDASK method before any release claim.

## Testing / rollback

17 hermetic tests verify exact 18/11/7 split, source paragraph/phase and direction symmetry, true-range-versus-ATR caveat, strict M15 causal pivot constraints, seven no-fabrication gaps, redacted output, no fake digest acceptance, one/all selected pairs 2/22 P184 proposal rows but 0 approvals, no mutation of original blank P184 template, forged config permissions fail, no vendor/Drive/broker operations. CI requires exact-head Python 3.11/3.12 with all original Forex source golden/security/cross-Python wheel, squash-only protected main and independent postmain CI.

**GO/NO-GO still blocked** by authenticated source owner original numerical approvals #45/#62, legitimate real quote/Drive data retention / BIDASK #27, P171 D1 source revision publisher-first-known #180 and independent chronological OOS #138. A research-only candidate may be shown as such, but not a verified actionable Forex signal. Nov 22 is a user-requested conditional deadline and does not waive evidence.
