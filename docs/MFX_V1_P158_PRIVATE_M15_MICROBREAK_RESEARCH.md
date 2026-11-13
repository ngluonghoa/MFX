# MFX P0.158 — sealed M15 private micro-break arithmetic (research only)

Date: 2026-11-14 ICT. Parent accepted P0.157 protected main `4c5b174742bf642b4f01fa13f11f02477c05041c`. Scope is independent of frozen Forex 102 source blobs, 11 SOURCE_LOCKED Google Docs, existing GitHub Actions cache schedule, OAuth/Drive permissions and broker connectivity.

## What is new (functional arithmetic, no speculative signal)

The source-derived P0.155 closed MID candle histories and the P0.156 already right-candle-confirmed candidate pivots are reused in the **same memory**. Two explicitly unapproved sensitivity profiles (1-left/1-right and 2-left/2-right) independently inspect the latest CLOSED **M15** bar. A strict experimental up-cross requires prior M15 close <= previously confirmed HIGH and latest M15 close > HIGH; down-cross requires prior >= previously confirmed LOW and latest < LOW. The known pivot's right confirmation candle MUST have closed on or before the latest M15 candle OPEN. Equal or already-crossed prices do not create a new experiment event. Missing/stale M15 cannot silently use M5, H4 or D1 substitute bars. Private Decimal crossing kind, level and closing price are never included in public GitHub Actions output.

The existing six-TF sealed archive consumer computes this private receipt with **no extra Drive GET, provider call, write, workflow, cron or feature flag activation**. Its disabled owner-gated manual GET-only report exposes only bounded profile availability/status, not direction, threshold, price, event or private input hash. The P0.157 36-row source-owner crosswalk remains intact: this M15 micro-break is a useful technical precursor, **not** the original source-owned B2/S2 micro-break policy.

## Release stop and missing authorities

Original Forex B2/S2 numeric choices still 0/36 signed; 14 other MFX entry candidates still not source-numeric qualified. H1 support/resistance origin and ATR/anti-chase boundaries, D1 2026-11-11 numeric correction quarantine (#147), licensed provider account rights to raw/derived Drive data, publisher first-known/revision, BID/ASK spread/slippage/fees, original structural SL/TP/net R and true historical OOS are NOT satisfied. Closed UTC does not attest when the vendor published the data. All outputs externally stay `NO_SIGNAL / UNVERIFIED`; no broker, no live BUY/SELL or release promotion.

## Acceptance and rollback

Use GitHub PR exact-head Python 3.11/3.12 full CI, frozen source SHA/golden/static/security, 20 new hermetic positive/negative cases, cross-Python wheel and independent postmerge main-push CI. Reject a forged numeric/source permission or tampered private input receipt. Roll back only these MFX-owned research, tests, report projection and pinned baseline SHA exceptions; do not modify original Forex source or sealed market archives. This study is synthetic test evidence, not licensed live market proof.
