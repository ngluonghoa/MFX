# MFX P0.159 — private chronological M15 prefix replay on SHA-sealed source

Date: 2026-11-14 ICT. Parent code/QA checkpoint: PR #159 protected main `97049e9c2183373de860890f92ffb27d16e4a6a0`, native main-push CI https://github.com/ngluonghoa/MFX/actions/runs/43487670210 independently PASS.

## Real functional change

P0.158 computes the **latest** M15 closed-bar crossing against a pivot whose right-confirmation candle had already CLOSED before that M15 OPEN. P0.159 extends that same trusted in-memory computation into a **chronological per-prefix research replay**, not a new price source or signed strategy policy. For each 1/1 and 2/2 unapproved SIM sensitivity profile, P0.159 runs the exact P0.158 decimal crossing logic on every available M15 CLOSED prefix whose length is sufficient; a later bar, future-confirmed pivot or later price revision cannot be used for a previous prefix decision. The final prefix must independently match the P0.158 latest result or fail closed.

Input is the same existing P0.155 archived multi-candle SHA source, P0.156 verified pivots, and P0.158 private microbreak. P0.159 recomputes P0.158 and the source SHA validation before replay to reject forged owner permissions, untrusted history, or overwritten latest receipts. No synthetic Forex MarketBar is made from real MID vendor data, no new Drive GET or Twelve Data request, no writes, no workflow/secret/cron changes, no broker, no local Mac/MOCHI. Results are private repr-hidden `PrivateM15PrefixObservation` values; public manual Drive JSON is unchanged and does not include directions, levels, intermediate events, SHA source fingerprint, or prices.

## Important limits — NO fake OOS

This is **as-of technical CLOSED-candle prefix replay of the currently cached snapshot**, not independently captured historical vendor first-known or authentic point-in-time source revisions. The native Sydney D1 2026-11-11 OHLC source divergence remains HOLD Issue #147; source account licensing including private Google Drive raw/derived retention and public display is not established. No original Forex source-owner numeric predicates (B2/S2 0/36) or the other fourteen entry models are approved. Real BID/ASK/slippage/swap/news/contract/net R:R, strategy-specific broker session calendar, untouched true chronological OOS and source-qualified six-frame freshness are not accepted. The public output remains `NO_SIGNAL / UNVERIFIED` and no broker order is enabled.

### Public vendor licensing review (not account authorization)

Official Twelve Data Terms https://twelvedata.com/terms distinguish permission for internal processing/storage subject to plan/time restrictions, derived non-reconstructable data, non-display permission by tier and separately licensed redistribution. Twelve Data Forex v2 https://support.twelvedata.com/en/articles/12520817-forex-api-v2 describes composite/aggregated MID candles and WebSocket mid updates; no broker-executable BID/ASK or independent publisher revision first-known proof follows from those descriptions. Twelve Data commercial/personal usage https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage explicitly distinguishes individual vs business usage. Actual customer plan, product entitlement, raw and derived Google Drive retention, replay, publication, quote sides, source revision contract and deletion-on-termination must be evidenced by account-specific written documents before promoting signals. Do not call external vendor or create new quoted-market archive from this review.

## Acceptance and rollback

20 Cloud-hermetic new tests verify per-prefix monotonic close time, same-profile final equality, controlled UP/DOWN actual Decimal arithmetic, no future level, already-crossed boundary, stale M15, forged data rights, private source SHA tamper, public privacy, determinism and exact zero new side effects. Full existing 3260 tests per Python 3.11 and 3.12 plus golden Forex 102-source SHA lock, static/security checks, wheel parity and independent exact protected-main postmerge CI are release prerequisites. Rollback only P0.159 MFX-owned code/test/doc and exact exception SHA ledger, not original frozen Forex or existing source archives.

Next real release gate: authoritative owner-signed B2/S2 formulas/units and source as-of semantics using **existing P0.35 intake** (do not duplicate), provider-specific lawful quote and retention rights (Issue #27), D1 owner adjudication #147; then integrate causal multi-TF zones, Bid/Ask economics and untouched OOS. No code module can grant these approvals itself.
