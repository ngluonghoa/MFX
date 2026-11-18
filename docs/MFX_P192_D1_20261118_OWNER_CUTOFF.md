# MFX P0.192 — Owner-selected native EUR/USD D1 restart on 18 November 2026 (Sydney local)

**Owner decision:** 18 Nov 2026, ICT: “Bỏ qua đi, lấy D1 từ ngày 18/11 đi.” This means **ignore D1 dates before 2026-11-18 for the NEW, owner-selected D1 cache epoch**, not erase previous immutable evidence or falsify historical source publication.

## Time contract and first permitted fetch

D1 originates from provider-native `1day` EUR/USD MID with **Australia/Sydney local session labels**. The 18 Nov Sydney session ends at **2026-11-18 13:00 UTC / 20:00 ICT** (Sydney UTC+11 in November). Existing 2m15s publication buffer means no NEW D1 fetch may be scheduled before **13:02:15 UTC / 20:02:15 ICT** on 18 Nov. The hourly native writer runs at UTC :25; its first eligible *scheduled* opportunity is the :25 run after close, if GitHub actually triggers it, the provider returns the closed candle and the normal quota and Drive gates pass. A GitHub schedule is best effort; no fixed delivery time is guaranteed.

## Scope of the cutoff

1. The existing 102 source Forex 1.0 Git blobs, 11 SOURCE_LOCKED Docs, old V1 native D1 sealed archive, P169 quarantine observations and P171 fresh epoch since 11 Nov remain **unaltered** and separately verifiable.
2. A new, **disjoint immutable Drive filename prefix and manifest schema** `MFX_P192_EURUSD_D1_20261118_FRESH_EPOCH_V1_` and `MFX_P192_D1_FRESH_EPOCH_V1` stores **only closed Sydney date labels 2026-11-18 onward**. A first completed provider-native 18 Nov candle is mandatory for root. Old provider rows (11–17 Nov) may arrive in the API response but are not admitted into this archive.
3. The new root SHA parent is bound to the SHA-verified immutable **original V1 D1 manifest**, not to a rewritten or silently accepted P171 version. Later appends require matching SHA for all recent P192 overlaps, full P192 source-archive audit and readback, closed local dates, quota and independent full V1 archive re-audit.
4. The old P171 11-Nov data may still be read in separate **archival** audits but **must not be selected as the active new D1 source**. Read-only audit gives explicit `P192_WAITING_FOR_FIRST_CLOSED_20261118_D1` before first seal, or `P192_D1_20261118_FULL_SHA_READONLY_ACCEPTED` after an independently verified seal. It preserves P171 archival receipts separately.
5. Existing hourly writer (UTC :25) and native read-only audit (:45) are reused. No extra cron or per-hour vendor polling, no new Drive folders or account secrets, no broker orders. H4 native writer and its original source SHA semantics remain intact.
6. **If the new 18-Nov candle itself is subsequently revised**, P192 still detects mismatched overlap SHA and quarantines the new epoch. Owner choosing a cutoff does not authorize infinite reset/overwrite.

## Signals and limitations

- This is a deliberate **prospective collection epoch**, not proof that revised vendor history was correct, a historical backtest backfill, or source publication timestamp attestation. Historical owner-cutoff before/after dates cannot be used for causal as-of replay. The original historical revision incident remains auditable in [#180](https://github.com/ngluonghoa/MFX/issues/180) but no longer determines P192 *initial* root eligibility. New P192 revisions remain fail-closed.
- Only one newly collected D1 candle is insufficient to establish D1 pivots/trends. **No automatic promotion of prior P171/V1 D1 bars into the new active epoch** to manufacture an H4/D1 trend or bypass preconditions.
- Source-owner 36 B2/S2 numeric approvals [#45](https://github.com/ngluonghoa/MFX/issues/45), account/tier-specific licensing + BID/ASK execution rights [#27](https://github.com/ngluonghoa/MFX/issues/27), untouched historical OOS/SL/TP/net-R and release governance [#138](https://github.com/ngluonghoa/MFX/issues/138) remain STOP. Public still `NO_SIGNAL/UNVERIFIED`; zero automated trading.
- Real live acceptance requires a **naturally scheduled post-close source fetch and independent read-only full P192 SHA audit**. Passing CI alone cannot assert the Drive epoch was created, a candle returned, or the provider's true publisher-first-known information.

## QA and rollback

Full GitHub CI must pass on PR head and independently on squash-only main: both Python 3.11 and 3.12 tests, original source Golden/SHA, approved Git-delta manifest and wheel parity. Scripted tests validate Sydney boundary, no premature vendor call, first root 18-Nov only, immutable SHA replay, source revision holds, prior archive isolation and actual hourly writer path. If there is a failure, rollback only the workflow selection and P192 code using a new governed PR; preserve all already sealed objects and original source evidence.
