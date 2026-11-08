# M2/P0.1 — Source candidate and usage-rights review (2026-11-07)

**Status: PUBLIC TECHNICAL DOCUMENTATION CHECKED; ACCOUNT-SPECIFIC RIGHTS NOT VERIFIED. No real market data collected, cached, downloaded or used for Backtest.**

## Engineering decision
Public API docs, a working connected API key, declared product coverage, historical price timestamp semantics, and a right to retain or backtest data are **different claims**. Never infer one from another.

The new `src/forex_trading/source_qualification.py` provides **strictly read-only**:
- A typed public capability claim: provider/product/instrument, *historical* feed model, BID & ASK components, M1/M5/M15 availability, timestamp semantics, account-vs-historical pricing parity.
- Rights evidence **per distinct use**: API_ACCESS, STORE_RAW, DERIVE_BARS, HISTORICAL_REPLAY, INTERNAL_BACKTEST, CACHE_INCREMENTAL. REDISTRIBUTE is separate; no inference from internal analysis.
- Document basis and SHA-256 evidence descriptor, first-known UTC, expiration, denial/unknown/duplicate/future-known and price-side checks.
- Even a perfectly filled **CLAIMED** packet is only `review_packet_ready`; flags `vendor_entitlement_independently_verified`, `may_ingest_real_data`, `may_cache_or_store_real_data`, `may_run_real_backtest` are all **always false**, pending external legal/account and actual source verification. No API credential is stored.

## Public-source candidate evidence — NOT a license or vendor endorsement

| Candidate | What public/official documentation supports | Critical OPEN gates | M2 current verdict |
| --- | --- | --- | --- |
| **OANDA v20 REST** | Official [candles endpoint](https://developer.oanda.com/rest-live-v20/pricing-ep/) and [candlestick definitions](https://developer.oanda.com/rest-live-v20/instrument-df/) expose separately requested `bid`, `ask` and `mid` OHLC candles; official granularity includes M1/M5/M15; alignmentTimezone/dailyAlignment are request parameters. | OANDA official [troubleshooting](https://help.oanda.com/us/en/faqs/rest-v20-api-troubleshooting-guide.htm) warns historical candles may use a base-price group different from **account-specific live prices**. Requires account/API token & regional eligibility; broker terms for backtest/retention/replay, event first-known/revision capture, audited native BID+ASK M1/M5 sampling, account-price parity, tick-level fill ambiguity. | **PUBLIC_TECHNICAL_POTENTIAL; ACCOUNT/RIGHTS/PRICE_PARITY UNVERIFIED; BLOCKED** |
| **Dukascopy / JForex** | Dukascopy's official [IHistory](https://www.dukascopy.com/swiss/docs/interfaces/IHistory.htm) describes historical bars and ticks with BID/ASK `OfferSide`; official [FAQ](https://www.dukascopy.com/swiss/english/about/faq/) describes stored best BID/ASK, ticks/minute/hour/day sources, other periods reconstructed by their platform. | Explicit provider/license permission for raw retention, derived bars, persistent caches and backtests; interface/account/location availability, 1-minute BID/ASK test, timestamp/revision first-known, session rollover, research redistribution prohibition. A third-party downloader's capability does not prove rights to underlying data. | **PUBLIC_TECHNICAL_POTENTIAL; RIGHTS/ACCESS UNVERIFIED; BLOCKED** |
| **Twelve Data** | Official [Forex catalog](https://twelvedata.com/exchanges/physical_currency?group=core) and [API Docs](https://twelvedata.com/docs) describe forex historical `/time_series` OHLC, exchange rates and quote endpoints. Connected `get_api_usage` returned quota/plan information on 2026-11-07; quota access is **not** a contractual grant. | Public material checked does **not establish separate native historical BID+ASK candles or bid/ask ticks**, nor source revision, account parity, store/derive/replay/backtest rights. Do not reinterpret generic OHLC as bid+ask. No historical bars requested pending rights review. | **GENERIC_OHLC_DOCUMENTED; TWO_SIDED_PRICE_MODEL UNVERIFIED; BLOCKED** |

## M2 required external evidence (NO secrets in repository)
1. Exact vendor, jurisdiction/account product, instrument mapping and documented product agreement applicable to the authenticated user.
2. Explicit account-specific right to access, retain raw, cache, create derived bars, replay and run internal Backtest. Separate redistribution/transfer rights.
3. Historical native BID/ASK samples with compatible stream/revision provenance, timeframe and first-known clocks, source-versus-account pricing deviations, gaps/spreads/DST/session completeness.
4. Independent evidence against true vendor terms and source bytes; source/time-calendar provider validity. Revocation/expiry review, retention period, incident and deletion policy.
5. Approval to connect read-only, cost/credit bounds and persistence/storage location before bulk acquisition.

## What's NOT done
No live broker integration, no automatic order, no source normalized bar ingestion, no external vendor contract review, no real tick data, no Backtest/OOS or broker fill/cost analysis. Source qualifier cannot be bypassed by a self-asserted claim. User approval must precede vendor API use beyond already performed read-only usage/quota check.
