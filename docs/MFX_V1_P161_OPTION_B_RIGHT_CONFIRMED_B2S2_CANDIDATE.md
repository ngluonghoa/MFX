# MFX P0.161 — Option B: D1/H4 + M15 right-confirmed B2/S2 numeric candidate

**Development acceptance only**, dated 2026-11-14 ICT. Parent approved P0.160 protected main `152772fd8c194b6f23f5d91201a4d62ce6c09daf`, [PR #161](https://github.com/ngluonghoa/MFX/pull/161), independent main CI https://github.com/ngluonghoa/MFX/actions/runs/43504135383 Python3.11+3.12 3,304 tests each + wheel PASS.

## Why this patch matters

The first independent MFX Option B numeric draft P0.160 took D1/H4 trend from a **two-candle higher high/low proxy** and took a micro-trigger level from a single preceding M15 seed candle. Neither is a source-authored numerical Forex rule, a valid two-confirmed-swing structural trend, nor a right-confirmed prior pivot. P0.161 replaces **this actual weakness** in a newly versioned MFX-only synthetic B2/S2 candidate: it does not merely add another standalone M15 study.

P0.161 **extends existing** `mfx_research/confirmed_swings.py` (P0.20) to scan M15 using its already tested strict left/right price extrema logic and source FIRST-KNOWN/RETRIEVED/closed-right-bar checks. The existing P0.20 D1/H4 swing calculations and `trend_from_confirmed_swings` are reused unchanged. A backward-compatible optional M15 confirmed-history/policy input validates exact source-pair/calendar/provider/stream and the latest stored seed identity. Only a last right-confirmed high (B2) / low (S2) available before the first trigger M15 OPEN can be used as micro-break level. Missing high/low, later-right-known, revised/unlicensed, mixed stream, gaps and premature candles **fail closed**, never substitute a guessed recent candle. The existing D1/H4 trend function already requires **two independently confirmed HIGH pivots and two independently confirmed LOW pivots per TF** to call UP or DOWN. If this cannot be proven, the existing P0.18 result is NO_SIGNAL instead of inventing a trend.

Then the new `mfx_research/mfx_b2s2_confirmed_policy_v2.py` composes existing P0.20 full D1/H4/H1 causal derivation and P0.18 strict M15 CROSS + ATR near/anti-chase gate, and the existing P0.31 original 22-role SIM classifier — it does NOT clone their arithmetic. It must emit private B2 BUY or S2 SELL experimental candidates from actual synthetic bars before routing an unverified research event; output `NO_SIGNAL / UNVERIFIED` is hard-fixed regardless.

## Draft profile, versioning and approved scope

- New v2 strategy ID: `MFX:B2S2-NEW-STRATEGY-DRAFT-002`, `docs/MFX_V1_B2S2_CONFIRMED_SWING_DRAFT_V2.json`.
- Parent candidate five H1/near/width/chase numbers pinned to the exact unchanged P0.160 Git blob `dbaed8ca436904fd83c528818358e677def43be3`; numbers 3, 3, 0.3, 0.5, 0.5 still uncalibrated and **not approved** for live trading.
- New independent pivot research widths: D1/H4 1 left/1 right; M15 1 left/1 right. A complete, chronologically right-confirmed sequence with 2 highs and 2 lows per higher frame is required; the 1/1 width itself is **only an unapproved experimental MFX-specific starting choice**, not an authorized strategy numeric setting.
- Same synthetic MID source, simulated UTC periods, simple mean True Range (NOT Wilder ATR). No lawful real native D1 session, real first-known evidence or broker BID/ASK rights are assumed.
- Immutable original 102 Forex Git blob sources and eleven SOURCE_LOCKED Google Docs unchanged; no claim to numeric Forex 1:1 parity where source defines only `MANIFEST_DRAFT / SPEC_PENDING`. Owner-selected Option B authorizes new MFX-only development but **does not approve** numeric values or public BUY/SELL.
- 28 new pure hermetic SIM positive/negative/boundary tests, plus all existing 3,304 regression tests each Python 3.11+3.12, crosswheel/frozen source/security, and independently green exact protected-main postmerge CI required before engineering acceptance.
- No new real vendor API, Drive GET/write, quote cache rewrite, schedule, secret, broker order, Mac/MOCHI/local/ChatGPT automation. No change to existing hourly source writer or P059 D1 quarantine.

## Real-world gates and next work

This completes a **genuine right-confirmed structural candidate**, but production needs data. Actual H4/D1 native sessions and 2026-11-11 D1 changed OHLC under [#147](https://github.com/ngluonghoa/MFX/issues/147) remain HOLD: original immutable SHA archive may not be silently overwritten or treated as first-known at the old decision. Exact subscription and rights for private raw/derived Google Drive retention/replay + display and quote sides under [#27](https://github.com/ngluonghoa/MFX/issues/27) still need independently attributable evidence. Source first-known/revisions, real publisher-trusted MID semantics, H1 zone calibration, real BUY ASK / SELL BID fees, spread/slippage/swap, structural SL/TP/net R:R, event dedup, native D1/rollover calendar, sufficient **untouched true historical OOS** and separate approval of MFX v2 numeric policy are still not done. No signal release or trading remains allowed; status `NO_SIGNAL/UNVERIFIED`.

Rollback revert the four new v2 MFX-only artifacts and the reversible P0.20 optional M15 extension, preserving P0.160 and source-locked original Forex, Drive/caches/workflows unchanged.
