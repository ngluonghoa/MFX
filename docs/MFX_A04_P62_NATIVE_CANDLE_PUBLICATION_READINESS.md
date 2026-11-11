# MFX A04/P0.62 — Conservative provider candle publication readiness for native H4/D1

Date: 2026-11-11 ICT. Scope: EUR/USD source-native H4 4h UTC time-axis and D1 Australia/Sydney source-local session date, staged P0.59 manual incremental source writer, and the P0.60 manual Drive-only preview. This is a scheduling and quota-safety correction; it is **not** activation of any native periodic writer or a modification of M5 V2.

## Source-driven finding (not owner account entitlements)

Twelve Data's published **Data delays** guidance (2026-01-23) reports a **typical REST candle availability delay of 0.3–2 minutes after a candle closes**, depending on the instrument. Source: https://support.twelvedata.com/en/articles/5203307-data-delays. This is an illustrative typical interval, **not a guarantee** that a particular EUR/USD 4h or D1 source candle is immediately available at exactly two minutes.

Existing MFX native parser `H4_CLOSE_GRACE=15 seconds` is a **minimum close-validity filter**, not a promise that the upstream /time_series candle has been published. Former P0.59 planner used the same 15-second H4 grace to decide when to spend an external price request. At an hourly or daily boundary that could create an unnecessarily early price call, followed by a valid but stale no-new-candle response. The immutable SHA store already handled the stale response accurately, but the call consumed credits.

The Twelve Data **Forex API v2** support article documents 24/7 coverage including weekends/holidays (https://support.twelvedata.com/en/articles/12520817-forex-api-v2), consistent with weekend H4 labels present in the existing EUR/USD native H4 archive. This document does not claim every /time_series API variant or account independently guarantees a weekend candle; do **not** impose an arbitrary classical broker FX trading-week calendar in this cache, nor fabricate missing weekend data.

## P0.62 technical design

A constant `SOURCE_PUBLICATION_BUFFER = timedelta(minutes=2, seconds=15)` is applied **only** to the deterministic native incremental fetch planner `mfx_cache/native_htf_incremental.py`, reused by both the staged P0.59 manual writer and the P0.60 manual read-only preview. No change to the original source-native parsing contract, P0.55 initial writer, M5 hourly writer, source-locked 102 Forex blobs, provider credentials or GitHub Actions workflow scheduling.

- **H4 UTC:** select the most recently eligible closed 4h candle using `ready = now_utc - max(H4_CLOSE_GRACE, SOURCE_PUBLICATION_BUFFER)`, then compute its actual H4 UTC 00/04/08/12/16/20 open time. An H4 bar closed at 08:00:00 UTC is *not due for a new vendor price request* at 08:00:16 or 08:02:14, but becomes due at 08:02:15 UTC. A source response can still be stale, and immutable SHA overlap rules still apply.
- **D1 Australia/Sydney:** compute the IANA-local date of `now_utc - SOURCE_PUBLICATION_BUFFER`, then subtract one date. Subtract in UTC **before** converting to Sydney for consistent DST transition behavior. A Sydney session ending at local midnight becomes eligible for a source request at 00:02:15 local, not 00:00:01.
- **Both:** If the archival last native label is at least as recent as the latest *eligible* slot, return `NO_NEW_CLOSED_SLOT_NO_VENDOR_CALL`, with **0 price calls, 0 /api_usage calls, 0 Google Drive writes** in P0.59. Otherwise preserve existing price-call limit (0/1/2 selective), 24..120 outputsize, strict source-native OHLC/schema, 16 pinned SHA-overlap candles, quota checks, append-only Chunk+Manifest, post-write readbacks and P0.60 truthful receipts. No automatic broker action or BUY/SELL signal is introduced.
- **No false finality claim:** The 2m15 buffer is a cost-control policy based on typical delivery latency. An exceptionally delayed candle may remain unavailable; source-stale response is reported separately and never falsely described as a newly written candle. The existing P0.58 read-only full SHA audit remains hourly and is not moved to 2m15.

## Reproducible deterministic QA

`tests/test_a04_p62_native_publication_buffer.py` contains **20 hermetic no-network tests**:
- H4 15s and 2m14s hold vs exact 2m15s release; already archived slot remains skip; 4h UTC label preserved.
- D1 Sydney midnight 00:02:14 hold vs 00:02:15 release; explicit DST start (Oct 4 2026) and end (Apr 5 2026) in IANA Australia/Sydney; D1 does not receive an artificial H4 UTC timezone override.
- Both H4+D1 due simultaneously, only-one-window due, prior lag still fetches even when the newest session waits for publication, bounded outputsize, no bogus weekend calendar, parser still excludes an unclosed H4 bar.
- Original P0.59 boundary test is updated from 15 seconds to 2m15s while H4 source-parser 15-second close validation remains verified unchanged.
- Manual staged writer workflow keeps `workflow_dispatch` only and independent fourth variable `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED` remains owner-controlled.

## Vendor licensing assessment (must not infer personal entitlements)

Official Twelve Data Terms of Use (updated January 1, 2026): https://twelvedata.com/terms. Section 2.2 permits receipt/processing/storage for authorized **Internal Use**, but section 2.3(g) prohibits caching beyond vendor-prescribed limits, and section 16.1 ties retention to the actual subscription and third-party data restrictions. Twelve Data's commercial/personal article (https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage) distinguishes individual vs business use and redistribution.

**Account-specific MFX license tier, Forex data retention maximum, third-party source terms, and any redisplay/redistribution permission remain unverified**. This PR does not assume a blanket right to indefinitely keep immutable raw OHLC on Google Drive. The operator should verify the plan and permitted retention with Twelve Data before adopting long-term scheduled archival or external sharing; immutable audit semantics may need an expressly authorized retention policy. No delete or overwrite operation was added here. Do not assert that technical success proves license compliance.

## Acceptance and deployment boundaries

- Hosted PR full Python 3.11+3.12 unit/negative tests, source-locked Forex parity, static/security and cross-Python wheel parity; **independent exact protected-main push CI** after merge required. Exact Git blob SHA pins tracked via `docs/MFX_ALLOWED_BASELINE_DELTAS.json`.
- P0.55 real native root write PASS, P0.58 real scheduled read-only audit PASS, P0.60 real manual Drive-only preview PASS, P0.61 hosted full SHA/4h UTC grid CI PASS. Those proofs remain independent of P0.62.
- **Do not enable** `MFX_NATIVE_INCREMENTAL_WRITER_ACCEPTED`, any H4/D1 cron, HOT V3, broker trading or source-numeric signals as part of this PR. P0.59 real incremental writer remains pending separate owner-controlled four-way-gated manual dispatch and verification of new native Manifest SHA, provider quota, full historical provenance and M5 isolation.

## First hosted PR CI QA correction

Initial PR #104 CI #42990421300 completed **1966 unit tests PASS on Python 3.11 and 3.12**, but its Ruff E741 lint stage correctly rejected the new test fixture's one-letter variable `l` as ambiguous. The fixture now uses `label` and must be re-pinned by exact Git blob SHA. The first CI is NOT accepted; only a subsequent all-green latest-head PR check followed by an independent protected-main push CI can authorize the P0.62 checkpoint.

## P0.64 hourly operational integration (supersedes historic manual-only label)

The pure `SOURCE_PUBLICATION_BUFFER=2min15s` native source planner remains identical; the same P0.59 manually accepted writer now also executes from owner-approved GitHub Actions **UTC :25 hourly schedule**, with manual fallback. GitHub actual execution time, not cron's nominal timestamp, determines H4 and Sydney-local D1 readiness. No H4/D1 price request if no newly eligible closed slot, and the D1 session ending midnight Sydney cannot be requested until its 2m15s publication buffer has elapsed. P0.64 does not change data values or create a new cache backend; SHA, 256-object preflight, quota headroom and read-only auditors remain independent. A hypothetical D1 at 2026-11-12 00:02:15 Australia/Sydney becomes eligible for the next UTC 13:25 hourly run (20:25 ICT 2026-11-11), not for an immediate forced vendor request. No broker or HOT V3. Documentation: `docs/MFX_A04_P64_HOURLY_NATIVE_H4_D1_AUTOMATION.md`.
