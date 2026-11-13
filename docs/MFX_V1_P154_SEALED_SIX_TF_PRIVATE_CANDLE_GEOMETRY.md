# MFX v1 / P0.154 — actual six-frame CLOSED MID candle geometry from sealed read-only archive

Date: 2026-11-13 ICT. Parent owner-approved OHLC-first and optional licensed API BID/ASK decision PR #153, protected main `c89e7c7fcbf6f8547eeba20560d0d83d1574d796`. Signal-only critical path #138, licensed source #27, source-owned B2/S2 0/36 #45, native D1 restatement #147 OPEN/HOLD.

## Why this is functional analysis and not another mode declaration

New pure `mfx_research/six_tf_private_candle_geometry.py` consumes the existing typed `SealedArchiveSixTFReceipt` from existing native M5/H4/D1 and complete M5-derived M15/M30/H1 six-frame read-only consumer. It runs the same sealed-source/required SHA-mode/metadata authority validations via P0.149, and P0.153's OHLC-first gate. For **every PRESENT, closed** MID frame, the engine actually parses strict finite positive `Decimal` OHLC and computes:

- exact candle high−low range, absolute close−open body, upper shadow high−max(open,close), lower shadow min(open,close)−low;
- close above/below/equal to open (zero-tolerance candle direction, NOT an entry signal);
- body/range fraction and normalized close location, each within [0,1] when range>0; exact zero-range candles return `None` ratios, NEVER division by zero;
- exact decomposition invariant range = body + upper + lower;
- per-frame original SHA *claim* association and private SHA-256 of all OHLC inputs, frame claimed SHA and existing source-fingerprint. This in-memory digest is not a vendor signature, independent SHA custody or proof that prices were first known at decision time.

The function requires proper six-frame membership/ordering, original closed native-vs-derived roles, source bar counts: M5=1, M15=3, M30=6, H1=12, H4=1, D1=1; exact expected time-basis; UTC end for intraday and no falsely invented UTC end for Sydney-local D1; no future frame relative to decision. It computes **only available frames** and explicitly retains missing/stale M5/M15; no stale gap backfill. These are per-latest-candle geometry facts, not a multi-bar EMA/trend, right-confirmed pivot, source-approved entry region, future price knowledge, verified spread or actual trading economics.

## Actual existing optional private Drive reporting integration

The dormant, owner-gated GitHub Actions `tools/run_mfx_v1_manual_drive_six_tf.py` now **actually runs** `compute_private_six_tf_candle_geometry` on the SAME previously retrieved sealed receipt (if separately and explicitly owner-enabled); prior P0.149/150/153 six-frame source and BID/ASK policy still run. The private `PrivateSixTfCandleGeometry` object is held in memory only. The PUBLIC-safe GitHub Actions JSON reports **only** `private_ohlc_geometry.status=COMPUTED_IN_MEMORY_NEVER_PUBLISHED`, count of actually computed present frames, missing/stale names, source-side MID, technical completeness and explicit false derived-data rights/strategy/SL-TP/trade claims. It MUST NEVER serialize raw candles, derived shape directions, calculated price differences/ratios, private numeric SHA or source credentials into public GitHub logs.

This has **zero** extra vendor/Drive API calls, new price writes, schedule changes, workflow authorizations, secrets, broker connections, side effects or historical rewrite. The original owner-only manual `READ_ONLY_NO_SIGNAL` workflow remains OFF unless source owner separately approves. The already authorized historical read is not re-run or represented as current. Native D1 numeric mismatch on 2026-11-11 remains P059 quarantine; no automatic revision acceptance.

## Independent gates / next milestone

Even with 6/6 frames the actual SIX frames are latest single candles, not sufficient data to derive a validated trend or original source strategy. Currently ORIGINAL B2/S2 0/36 quantitative owner decisions, 14 other entry rule families, licensed retention/derived-data rights, publisher first-known and clock revisions, live BID/ASK economics, M5/M15 intra-hour freshness, causal OOS and source D1 conflict remain NO-GO. No `BUY/SELL` output, no release / broker execution. The private arithmetic, without vendor rights, must not be exposed to public or redistributed; detailed geometry may only be used internally in separately permitted environments and pending authorization.

35 Cloud-hermetic test cases include real arithmetic for up/down/doji/flat bars, upper/lower wick, zero division, per-frame source count/time basis, future/non-UTC quote time, malformed/nonfinite/inverted OHLC, missing M5/M15 and source corruption, in-memory private SHA changes when numbers change, unchanged public source SHA, safe no-price/no-token log and always NO_SIGNAL. Acceptance requires exact PR SHA hosted Python3.11/3.12 full original frozen 102 Git blob parity, security/static, wheel parity and independent protected-main push CI. Rollback only new MFX-only module/QA/doc and existing manual safe report edit with exact SHA allowlist, leaving original Forex source and current Cloud archives untouched.

**Next after P0.154:** source owner quantitative B2/S2 rules and vendor retention/quote rights, then *multi-bar* causal signal features and legitimate historical OOS; do not disguise single-candle geometry as trend or original Forex parity.
