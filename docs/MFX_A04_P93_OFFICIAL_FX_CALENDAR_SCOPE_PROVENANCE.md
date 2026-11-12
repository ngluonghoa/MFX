# MFX A04/P0.93 — Scoped FX session provenance: why public weekend hours cannot waive Twelve Data candle holes

Research as of 2026-11-12 UTC. This milestone introduces *no actual source gap waiver*, no market-calendar attachment to production, no provider call, no Drive cache write, no workflow/cron change, no H4/D1 replacement and no BUY/SELL/broker change.

## First-party official pages inspected

1. **Twelve Data Forex API v2**, https://support.twelvedata.com/en/articles/12520817-forex-api-v2 — published **2025-12-03**, describes Forex API v2 service **24/7 including weekends/holidays**, mid-price updates and aggregated candlesticks. Critically, availability of the feed/service is NOT proof of a continuously complete 5-minute bar series, nor proof that the MFX subscription uses the v2 feed. This is the strongest provider-side *availability* reference, not a signed historical candle/session calendar.
2. **Twelve Data Timezones**, https://support.twelvedata.com/en/articles/5745849-timezones — published **2025-05-13**, Forex default timezone **Australia/Sydney**. MFX intentionally passes `timezone=UTC` for intraday `/time_series`, while native Sydney D1 remains separate. Timezone correctness is not market session evidence.
3. **OANDA US Hours of Operation**, https://www.oanda.com/us-en/trading/hours-of-operation/ — the broker's own trading hours show opening Sunday **17:05** and closing Friday **16:59** in New York, plus a **six-minute daily break**, with holiday/DST qualifications. This describes OANDA account **execution**, not the operating hours or candle emissions of Twelve Data's composite feed.
4. **CME Group 2026 FX Spot+ hours**, https://www.cmegroup.com/trading-hours.html — FX Spot+ venue schedule Sunday **17:00 CT** to Friday **16:00 CT** with a **daily 60-minute break**. This is specific to the CME venue/product; it is not a global FX spot/Twelve Data EUR/USD calendar.

No page above is a signed source-version-linked historical record of exact 48xM5 windows for the user's MFX feed. The *publicly observable* difference between Twelve Data's service 24/7 and broker/venue 24/5 is **scope divergence, not permission to skip missing candles**. The official Twelve Data v2 support article explicitly states 24/7 *operation*, not guaranteed weekend OHLC for every M5 bar. The provider subscription's actual v2 mapping and rights must be separately verified through approved evidence; never make a new price request merely to settle this during research.

## Current MFX code provenance (read-only)

The existing unchanged `tools/run_a04_p45_cloud_twelve_data_cache.py`, Git blob `5162b6068a5ba6bfa51d4fb1b57e81fd40a3a99e`, requests `https://api.twelvedata.com/time_series` with symbol `EUR/USD`, interval `5min`, timezone `UTC` (and the pre-existing user-supplied API key). This *source call shape alone* does **not** expose or certify the actual Twelve Data Forex API feed version, the subscription/license rights, 24x7 M5 candle completeness, or the exact provider historical holiday exceptions. P0.92 and the P0.66 live reader remain untouched.

The last independently audited point-in-time cache snapshot is P0.91 real P0.66 run #43138482666 attempt5: 41/41 bounded M5 manifest/chunk SHA, 492 fully closed M5 bars to `2026-11-12T10:00Z` with head `2676a0f5695c5639fb5a9d2800debb6d40cb3c0343e9d482144b3e3472f42ea1`, native H4 8/8 pairs and 9 exact complete H4 comparisons, zero mismatch. **P0.93 does NOT rerun the real cache audit or claim any later SHA.**

## Pure reference-scope review and negative QA

New `tools/mfx_fx_calendar_provenance.py` contains four immutable publisher URL/claim/scope records and a bounded, UTC-strict read-only gap classifier. It distinguishes:
- **DATA FEED AVAILABILITY** (Twelve Data v2),
- **DATA OUTPUT TIMEZONE** (Twelve Data Forex default),
- **BROKER EXECUTION** (OANDA US),
- **VENUE TRADING** (CME FX Spot+).

It validates the source-controlled MFX writer blob, source IDs, first-party article publication-date floor, exact UTC four-hour slot labels and sample bounds. Weekend labels are only UTC *candidates*. Public URLs are *not fetched or authenticated by this code*, and no HTML content SHA or publisher signature has been verified. The pure receipt always returns NO automatic weekend/daylight-saving exception, NO fresh market calendar evidence, NO H4 cutover, NO native request reduction, NO Sydney D1 change and NO numeric signals/broker. Source-specific calendar truth remains unresolved.

New `tests/test_a04_p93_fx_calendar_provenance.py`: **45** hermetic positive/negative cases for provider/broker/venue scope confusion, 24/7-versus-M5 SLA misinterpretation, source-ID/UTC/4H-grid/replayed-time/forward-dated article rejections, safe/no-price/no-Drive/no-broker.

## Acceptance boundaries / next

- Original Forex Trading baseline **102 source Git blobs**, 11 SOURCE_LOCKED Docs, existing M5 production writer, H4/D1 native workflows, cron, secrets, Drive records, provider calls, witness/CAS, B2/S2 owner gates remain unchanged. Source baseline trading is NOT executable broker signals or licensed BID/ASK.
- This research does NOT certify any official publisher historical page as monotonic, authenticated, content-addressed evidence. A reviewed browser page URL is **not** a cryptographically validated source version. Thus no actual missing M5/H4 bar can be reclassified as an authorized closed session.
- **Next P0.94:** design a separately approved, source-version-linked *signed or immutable* provider-calendar evidence admission policy (exact product/region/timezone/interval/date range, source custody/hash, actual API feed version, licensing). Build only offline fixtures and tests until owner approval. Keep native H4 until >=30 full H4 48xM5 comparisons across >=7 real days, verified gaps and separate owner GO. ChatGPT hourly task remains OFF; GitHub+Drive Cloud-only.
