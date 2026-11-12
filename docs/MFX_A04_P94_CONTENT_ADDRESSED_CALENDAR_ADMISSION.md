# MFX A04/P0.94 — Content-addressed FX calendar evidence admission (OFFLINE, NO-WAIVER)

2026-11-12, GitHub + Google Drive cloud-only engineering. This milestone builds a **pure research schema and fail-closed raw-byte SHA gate**, not a signed calendar, source entitlement, real provider feed/version verification, trading permission or H4-source cutover.

## What changes and why

The existing P0.93 code `tools/mfx_fx_calendar_provenance.py` distinguishes first-party Twelve Data Forex API v2 **24/7 data-feed service availability** from OANDA execution sessions and CME venue FX Spot+ hours. Those are *different semantics*. Public provider docs do **not** supply a signed versioned list of exact missing EUR/USD 5-minute candles. Even a perfectly well-formed source-claim JSON record with its own SHA does not prove that the issuer actually published it. Twelve Data source product is subscription-dependent; the unchanged MFX writer's `/time_series` query does not independently reveal the plan/feed version.

P0.94 adds `tools/mfx_fx_calendar_content_custody.py` as an isolated research-only gate:
- Accept only capped **32 KiB canonical, non-duplicate-key JSON bytes**, independently recalculate **SHA-256 over the actual supplied bytes**, reject digest spoofing, whitespace drift, unknown schema fields, invalid unicode/nonfinite/duplicate-key JSON or untrusted source URLs.
- Pin the **existing** MFX writer Git blob `5162b6068a5ba6bfa51d4fb1b57e81fd40a3a99e`, route `https://api.twelvedata.com/time_series`, exact `EUR/USD`, `5min`, `UTC`, `MID`, hypothesized `FOREX_API_V2` product. These fields are *checked as caller-declared scope*, not verified actual provider subscription.
- Validate exact UTC H4 boundaries, effective start/end exclusive, <=72 H4-slot coverage, closed observed H4 gap windows before review, source issuance/capture/review times, up to 72 label comparisons, and classification of missing requested closure labels.
- Distinguish a public **service availability** page from an **exact provider M5 closure claim**, even when a crafted byte payload *claims* the latter. An official reference URL is not a publisher signature. A self-reported SHA chain can be checked for structural parent/sequence/capture monotonicity while **external antirollback authority remains FALSE**.
- Return an immutable conservative `SnapshotCustodyReceipt` with **all operational permissions permanently false**: content SHA is not publisher identity, raw publisher page not authenticated, feed version not independently established, data licence not established, individual real candle exceptions not certified, no external monotonic witness, no owner GO, no automatic weekend waiver, native H4 and Sydney D1 untouched, no BUY/SELL or broker.
- Add **71 hermetic adversarial tests**, including synthetic source-scope spoofing, replay/chain swap, SHA tampering, calendar slot holes, weekday/weekend gaps, invalid timezone/capture, and I/O zero. Tests use **synthetic candidate JSON only**; there are no live provider-returned calendar snapshots.

## Authority boundaries

1. **Content integrity**: a matching SHA-256 confirms only that the candidate bytes equal a supplied digest. It does NOT prove the bytes came from Twelve Data. Even internally consistent self-reported parent hashes are not a signed external root.
2. **Publisher provenance**: obtaining a signed source-issued immutable data snapshot and verifying an independently trusted key, custody, data-rights and timestamp source requires a separately authorized workflow. P0.94 cannot perform this with a public support URL.
3. **Specific calendar waiver and H4 cutover**: require exact authenticated feed product/account/version, explicit M5 interval/EURUSD UTC data calendar, matching complete time windows, source rights, session/DST/holiday rules, >=30 exact closed 48xM5/native H4 windows in >=7 *real* days and explicit owner GO. P0.94 authorizes none of them.

Official facts cited as scoped references (NOT verified snapshot hash): Twelve Data Forex API v2 https://support.twelvedata.com/en/articles/12520817-forex-api-v2; Twelve Data timezone help https://support.twelvedata.com/en/articles/5745849-timezones; Twelve Data API timezone interval note https://twelvedata.com/docs/markets/market-state. These references concern API availability/timezone; none provide a signed historical EUR/USD 5-minute completeness calendar. The unchanged original Forex Trading 102 blobs and 11 locked source Docs remain frozen.

## Live state and next

The last independent P0.91 real bounded SHA audit remains GitHub P0.66 read-only attempt #5, M5 41/41 pairs, 492 closed bars to 2026-11-12T10:00:00Z, SHA `2676a0f5695c5639fb5a9d2800debb6d40cb3c0343e9d482144b3e3472f42ea1`; native H4 8/8, exact matched 9/9 complete 48xM5 H4, less than 30 windows/7d. **P0.94 does not authenticate any newer private Drive head**.

NEXT P0.95: separately assess owner-controlled evidence acquisition/review process for actual issuer-signed snapshots and permission evidence; do not turn on new provider polling or invent a calendar source, and do not change any workflow, cron, Drive data, prices, broker or source switch. ChatGPT hourly auto engineering task remains OFF, normal GitHub M5/H4/D1 cache tasks independent.
