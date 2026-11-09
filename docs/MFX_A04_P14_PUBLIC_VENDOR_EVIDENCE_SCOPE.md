# A04/P0.14 — Twelve Data official public documentation evidence, not user entitlement

## Why this checkpoint is different from P0.12 / P0.13

This is a **read-only review of actually published official Twelve Data documentation** on 2026-11-09; it does not generate synthetic quotes or pretend to verify current MFX subscription rights. Public webpages can change, so recheck them when requesting approval. The JSON evidence register is a snapshot, NOT signed terms, a vendor-provided private contract or execution authorization.

## Main evidence

- Official 2026 Terms of Use §2.2–2.3: internal receipt/processing/storage subject to subscription, caching only within permitted periods; §16 limits retention to subscription/third-party terms and states termination deletion obligations: https://twelvedata.com/terms
- Twelve Data Forex v2: composite weighted pricing, real-time **mid-price** updates and aggregate OHLC candlesticks. This does **not** establish native historical broker-specific BID/ASK: https://support.twelvedata.com/en/articles/12520817-forex-api-v2
- WebSocket docs show **BID and ASK where available**, including an example, but do not establish availability for all FX pairs, a historical BID/ASK API or broker-specific fills: https://twelvedata.com/docs/websocket/websocket-getting-started
- Forex /time_series OHLC and time range: https://twelvedata.com/exchanges/physical_currency?group=reference
- Historical time-series request windows and 5,000-point response limit: https://support.twelvedata.com/en/articles/5214728-getting-historical-data
- Personal vs business/redistribution permissions: https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage; plan/credits vary: https://twelvedata.com/pricing.

## Technical and rights decision

Seven P0.13 rights categories and eight P0.13 technical capability categories are each cross-linked to at least one official source and a specific written question for vendor/account entitlement. **No publicly documented capability automatically grants a user-specific right.** In particular, raw quote/candle chunk storage on Google Drive, replay retention, historical BID/ASK, first-known source revisions, product-specific availability, and paid Cloud credentials all remain **UNVERIFIED/BLOCKED**. Market data obtained for personal use cannot be assumed to be eligible for distribution or non-display production.

The canonical register is `docs/MFX_A04_P14_PUBLIC_VENDOR_EVIDENCE.json`, with ten source-backed findings, fifteen unresolved source/rights dimensions and six practical questions ready to send separately to vendor support/sales. No vendor message has been sent; user account/plan unknown. **No secrets, account names or vendor documents go into public GitHub.**

## Dev gates

Run `python -m tools.check_a04_p14_public_evidence` inside GitHub Actions to validate that the evidence register is anchored to the 46 P0.13 source-locked scenarios, contains only explicitly allowlisted public vendor URLs, includes every one of the 15 rights/capabilities, and forbids any positive rights, broker BID/ASK, live Drive cache, runtime or trading claim. These CI checks validate repository *claims and document consistency*, not re-fetch/approve legal terms. No source imports except P0.13 static gate, no real vendor API calls or subscriptions.

Keep protected-main PR review and independent postmain checks, 50 frozen Forex synthetic golden, P0.7 34 wrappers, P0.8 28-case STOP, P0.11 58 field gaps, P0.12 32 synthetic quote cases, P0.13 46 attestation cases, A03 coverage/mutation, strict mypy 30 core sources, security and cross-Python wheel. All MFX development remains GitHub/Drive Cloud-only. Zero src changes or trades. Do not modify original Forex Trading or MOCHIFX.
