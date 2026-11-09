# MFX A04/P0.18 — B2 LONG + S2 SHORT parametric synthetic research pilots

## Authentic source boundary

Original SOURCE_LOCKED_03_DETECTOR_AUDIT v0.7, B2 lines 28–38 and S2 lines 116–126 (frozen copied Google Doc https://docs.google.com/document/d/10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA/edit): B2 up-trend D1/H4, H1 support/ATR near-zone, early M15 higher-low or reclaim, confirmation past known micro-high and acceptable costs; S2 reversed down-trend, H1 resistance, early rejection/LH/BOS_DOWN, confirmation below known micro-low; both can invalidate. These are **qualitative draft source manifest requirements**. Exact trend/ATR/pivot/near/reclaim/chase/spread/TP/SL numerical policies are `SPEC_PENDING`, `CALIBRATION_NOT_RUN`, and `ACTION_ELIGIBLE_FALSE`.

The owner wants BUY/SELL analytical signals only, no broker order execution, with immutable 18-label catalogue (7 LONG, 8 SHORT entry candidates; B7 watch, S3/S8 exit only), and zero covert edits to original Forex source.

## Implemented and testable research code

`mfx_research/pullback_pilot.py` implements an **actual numerical microbreak predicate** for a two-bar closed M15 MID synthetic window:
1. Caller-supplied *claimed* D1/H4 structural trend agrees with B2/S2 direction, H1 support/resistance bounds and ATR are positive, finite and known before the prior M15 starts.
2. The prior closed M15 range is near supplied H1 price zone within an **explicit externally supplied, `SIM:` versioned** ATR multiple; no default.
3. Latest closed M15 close crosses a **previously known** micro-high (B2) or micro-low (S2), with explicit `SIM:` ATR anti-chase bound and no structural invalidation.
4. **Output B2 BUY / S2 SELL in research-only unverified evidence**, or NO_SIGNAL with precise reason. This is not Forex source-numeric equivalence; the known H4/D1/H1 structure and indicator values are caller-supplied synthetic fixture claims, not independently calculated. Neither numeric 0.5 ATR synthetic sample parameter nor chosen two-bar cross is **approved source strategy**; they are strictly unit-fixture data. Source H1 close/confirmation and live spread/fees/stop/TP may require additional gates and are *not proven*.

No real FX market inputs: immutable MarketBar MID with SIM: provider, version=1, synthetic entitlement, UTC first-known, closed complete quality verified as *fixture claim only*, revision and calendar/stream identity constraints. Fake provider or real entitlement rejected. No source-published signals, provider requests, Drive real cache, broker account or orders. Every candidate is `SignalStage.UNVERIFIED`, `source_verified_for_market=false`, `original_forex_numerical_parity=false`, `may_send_confirmed_signal=false`, `can_trade=false`.

Tests cover actual positive B2 and S2 numeric trigger paths, negative no-cross/contra-trend/invalidated support/far-zone/anti-chase, future context/market bar/retrieval, partial/open/quality, MID-side/timeframe, mixed stream/revisions, fake licensing/real-provider and invalid parameters. GitHub Actions proves code executes on Python3.11 and 3.12 and retains frozen source golden and all prior 941 methods. Research package remains **outside src/forex_trading and outside release wheel**.

## Next required steps (not falsely marked complete)

- Independently derive versioned D1/H4 trend, H1 zone/ATR and causal micro-level from actual source-qualified bar history; this P0.18 just validates supplied claims.
- Owner reviews and explicitly approves actual quantitative source-compliant parameter manifest and risk criteria for B2 and S2; no stock P01–P17 imports.
- Connect rule output to the safe P0.17 18-label taxonomy only as UNVERIFIED until source quality, first-known, economic/TP/SL, calibration and OOS are proven.
- External licensed OHLC/Drive cache rights are still blocked in GitHub Issue #27.
- No original Forex strategy parity/economic claim, no released software, no broker order/position integration.
