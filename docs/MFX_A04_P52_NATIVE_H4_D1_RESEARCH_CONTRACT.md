# MFX A04/P0.52 — native H4/D1 Forex source provenance (STAGED)

**Status:** Offline research schema only. No vendor request, no Google Drive cache file, no GitHub schedule, no BUY/SELL signal, and no broker. Retains MFX Cloud-only and the original Forex 1:1 source freeze.

## Why provider-native H4/D1

The existing V2 M5 writer explicitly derives only M15, M30, H1 from 12 closed M5 bars. It correctly rejects H4/D1 derivation. Twelve Data officially supports native `4h` and `1day` intervals. Its documentation explicitly states that the `timezone` parameter is valid only for intraday; for `1day` the provider ignores that parameter and returns dates in exchange-local time. Forex's default time zone is Australia/Sydney unless explicitly changed for intraday.

Official documentation:
- https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices
- https://twelvedata.com/news/april-2026-updates
- https://support.twelvedata.com/en/articles/5745849-timezones

The previous one-hour EUR/USD 12×M5 real cache proof and independent SHA audit remain unchanged; native H4/D1 are **NOT** active real caches.

## New pure contract

`mfx_cache/native_fx_htf.py` provides:
- `native_request_contract(symbol, "4h")`: exact `symbol`, `interval=4h`, `format=JSON`, `outputsize=120`, and `timezone=UTC`. It *plans* an intraday request but does not perform it.
- `native_request_contract(symbol, "1day")`: exact `symbol`, `interval=1day`, `format=JSON`, `outputsize=120`, with **no timezone request field**.
- `parse_native_forex`: pure validation of native vendor `meta.symbol`, `meta.interval`, `meta.type`, the IANA `meta.exchange_timezone`, bounded rows, date/time syntax, duplicate labels, strict OHLC ordering, and completed-candle-only inclusion.
- H4 dates use `UTC_INTRADAY_OPEN`, require a caller-declared `timezone=UTC`, and must pass **4-hour close + 15 second grace**.
- D1 uses `EXCHANGE_LOCAL_SESSION_DATE`; a daily `datetime=YYYY-MM-DD` value remains a **local session date**, *not* a fabricated UTC timestamp. The current exchange-local date is conservatively excluded.
- Each native candle carries explicit pair, interval, exchange timezone, source provider, `is_provider_native=true`, `source_numeric_strategy_approved=false`, `broker_orders=0`, plus deterministic canonical SHA256.
- Pair identity is parameterized (e.g., EUR/USD, USD/JPY), with exact response-symbol checks, **not** activation of any particular pair or new live fetch frequency.

## Important limitations before a real H4/D1 cache

- Provider-native time alignment/closure needs an authenticated actual GitHub-run payload proof per TF. In particular, D1 exchange-local candles **cannot** be called UTC daily candles.
- The parser's `requested_timezone` is a caller-side declaration, not proof that an actual HTTP request was made correctly. Any future adapter must pin and audit its real parameters.
- One provider native TF API call consumes credits; future scheduling must explicitly calculate both hourly and minute quotas across H4/D1 and additional pairs, respecting the existing EUR/USD M5 writer.
- Need separate immutable namespace per symbol/TF for Chunk/Manifest, exact SHA, parent-chain, readback, and idempotent duplicates/gaps before any Drive persistence.
- Weekend/holiday/session calendar is **not** supplied by this pure contract. Closed candle selection does not approve numeric signals or execution-grade BID/ASK.
- Twelve Data's long-term caching/retention rights are not independently verified. No change to current user-directed private cache or credential settings is made.

## Acceptance

1. Run the 27 offline contract tests on GitHub CI Python 3.11 and 3.12 and cross-version build parity.
2. Merge only after review to protected main and independently confirm post-main CI.
3. Next staged milestone should add a **manual**, private, masked-metadata-only native H4/D1 provider probe with strict credit protection (no vendor keys in logs); do not activate a new scheduled writer by default.
4. Only then design per-pair/per-TF Drive namespaces and real write/readback audits, keeping D1 local-session-date anchoring explicit.
