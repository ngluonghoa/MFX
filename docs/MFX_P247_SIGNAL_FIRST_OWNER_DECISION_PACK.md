# P247 — Signal-first decision pack (27 Nov 2026 ICT)

## Actual evidence and release disposition

P244–245 exact-main live witness [45938359025](https://github.com/ngluonghoa/MFX/actions/runs/45938359025) passed: 1404 GET, 391 M5 manifests, 256 raw tail hours, 74 H4 pairs, 16 private revised D1 snapshots. Seven joint-clock receipts, one bound setup with decision recheck, one H4-only deficit, one later H4 recovery but zero concurrent M15 recheck. P246 [PR246](https://github.com/ngluonghoa/MFX/pull/246) passed 4216 tests and squash main 23ae68506381d3473ea8eee5770d712013fec469. Independent main CI and P246 real receipt still required. This is technical evidence, not trading performance, publisher-first-known or source qualification.

Stop expanding clock-only diagnostics as release-critical work after P246 unless an actual correctness defect requires a fix. Preserve current hourly ingestion and source holds. Follow [#138](https://github.com/ngluonghoa/MFX/issues/138) and [#45](https://github.com/ngluonghoa/MFX/issues/45). No original numeric approvals (0/36). No original Forex source changes. No broker orders.

## Owner decisions, in review order

The following are existing P188 experimental methods, NOT approved original Forex rules. Review both directional expressions against SOURCE_LOCKED_03 and record ACCEPT FOR PROPOSAL, AMEND, REJECT or DEFER for each pair in the existing P184/P035 process. Accepting a proposal is not authenticated numerical source approval. If independent MFX semantics differ from Forex 1:1, explicit policy supersession is necessary.

| Requirement ID | B2 / S2 candidate | Unresolved decision |
|---|---|---|
| causal_d1_h4_trend | Both D1 and H4 higher highs/higher lows / lower highs/lower lows, two confirmed pivots each | Accept method only, calendar/revision still held |
| confirmed_pivot_left_bars | 1 closed left bar for HTF and M15, both sides | Review 1L |
| confirmed_pivot_right_bars | 1 closed right bar, both sides | Review 1R and causal first-known |
| h1_zone_origin_identity | min low / max high of lookback | Review anchor identity |
| h1_zone_lookback | 3 closed H1 bars | Review lookback |
| h1_true_range_atr_period | 3-bar simple mean true range for both sides | Explicitly NOT Wilder ATR |
| h1_near_zone_atr_multiple | prior closed M15 overlaps expanded zone, 0.5 x mean TR | Review near threshold |
| h1_zone_width_atr_multiple | support [anchor, anchor+0.3 x mean TR] / resistance [anchor-0.3 x mean TR, anchor] | Review width |
| m15_early_reversal_structure | near zone plus pretrigger 1L/1R micro pivot, mirrored | Review early structure |
| known_micro_break_confirm_rule | close crosses known micro high / low | Review strict closed crossing |
| anti_chase_max_atr_multiple | 0.5 x mean TR beyond frozen level, mirrored | Review chase bound |

Seven P206 remaining pairs do not have numerical proposals:

| Requirement ID | Must supply |
|---|---|
| structural_hl_lh_invalidation | confirmed structure, boundary buffer and invalidation rule |
| bid_ask_spread_and_cost_gate | licensed time-matched BID/ASK, cost ceiling, fee and slippage policy |
| session_dst_rollover_news_gate | authenticated session/DST calendar, rollover and news blackout rules |
| structural_sl_tp_net_r_gate | SL buffer, opposing structure TP policy, minimum net R, fill ambiguity |
| event_expiry_and_idempotence | closed M15 expiry count, origin/revision and persistent dedupe policy |
| licensed_source_first_known_revision | account-specific rights, immutable source revision admission, retention and publisher first-known |
| historical_walkforward_oos_qualification | licensed chronological history, splits, embargo, minimum sample and acceptance bounds |

Use exact P188/P206 and P184 source anchors; this table is only a compact review navigation guide. Keep the blank P184 canonical template untouched until actual reviewer input. P035/P184 external SHA is a reference, not authentication. Do not invent a digest or treat this document as a signoff.

## Parallel release-critical tasks and stop conditions

1. Complete P246 main CI, then one actual manual GET-only witness; no duplicate dispatch and no new scheduled jobs.
2. Owner review 11 existing candidate pairs and seven unresolved pairs, independently authenticate source approval before original numeric action. Distinguish 1:1 Forex and MFX independent research.
3. Obtain account-specific Twelve Data written retention/non-display rights (#27); existing user permission to save Cache does not replace vendor rights. Do not post customer secrets or send vendor inquiry without separate instruction.
4. Resolve D1 revision admission and publisher clock; preserve private P209 vintages and canonical quarantine. No hindsight.
5. After real approved rules and appropriate data, independent causal OOS / risk proof; no manufactured fill or after-cost result.
6. Until all gates pass, release disposition is **NO_SIGNAL / research demonstrator only**, not BUY/SELL production release. No broker integration.

No Cache optimization, new fetch cadence, source authority, price disclosure or background automation is authorized by this document. This checkpoint is review preparation, not closure of #45 or #27.
