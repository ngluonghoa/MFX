# MFX P0.163 — surface real D1 source-HOLD in manual six-TF NO_SIGNAL report

**Scope:** narrow MFX-only presentation integration after the accepted P0.162 real D1 quarantine. **Mode:** Cloud-only GitHub/GDrive; no provider calls or source restatement. 2026-11-14 ICT.

## Reproduced integration gap

P0.162 correctly suppresses all private price-derived research when the real EUR/USD Sydney-native D1 source is on Issue [#147](https://github.com/ngluonghoa/MFX/issues/147) HOLD. The preexisting manual Drive GET-only reporter still expected non-null private multi-bar/pivot/microbreak receipts and called geometry on technical frames. As a result, the known quarantined source could be presented as a generic renderer failure rather than an explicit readable source-fitness stop.

## Narrow fix

- The typed offline signal-only projection accepts **only** the exact P0.162 HOLD status, exact incident id, reviewed M5 anchor flag, active quarantine and suppressed-private flags, with all four private result fields **None**. It rejects undeclared/mismatched HOLD and any forged signal rights.
- The projected report explicitly carries `P059_NATIVE_D1_SOURCE_REVISION_QUARANTINE_NO_SIGNAL`, preserves SHA/count/freshness and frame-presence metadata, and distinguishes physical six-TF presence from source authority. No BUY/SELL, zone, entry, SL, TP, R:R or publisher first-known is inferred.
- The dormant owner-gated manual GET-only CLI returns a JSON-serializable **quarantine-only** report. It marks private feature/crosswalk/mode steps `NOT_RUN_D1_SOURCE_QUARANTINE`, and exits **2** after printing the explicit `MFX_V1_MANUAL_DRIVE_GET_ONLY_D1_QUARANTINED_NO_SIGNAL` marker. It never prints the normal `TECHNICAL_AUDIT_PASS` marker under HOLD. A malformed or forged report retains the existing redacted failure path.
- Normal synthetic research fixture presentation remains as before. These fixtures are **not real historical first-known/OOS proof**. The manual GitHub workflow still needs its separate owner gate and is not newly dispatched.

## Source and release boundaries

The original 102 frozen Forex blobs and 11 SOURCE_LOCKED Docs remain unchanged. P0.162 sealed consumer, existing Google Drive bytes, provider calls, GitHub schedule/secret settings, live Cache writers, source-native D1 quarantine, and numeric Option B strategy profiles stay untouched.

Issue [#27](https://github.com/ngluonghoa/MFX/issues/27) account-specific Twelve Data product/tier rights, Issue #147 publisher first-known/revision adjudication, owner numerical MFX-only strategy signoff, BID/ASK after-cost TP/SL/R:R and untouched chronological OOS are still **NO-GO**. No MT4/MT5, broker order or live BUY/SELL activation.

## QA and acceptance

Hermetic tests check the real-path source-HOLD using injected stores, explicit typed quarantine reason, no private computation, preserved custody evidence, redacted JSON, CLI nonzero exit, and strict rejection of forged HOLD, SHA and permissions. Existing normal-path regression must still pass. Accept only after GitHub-hosted PR and independent exact-main Python 3.11/3.12 CI, crosswheel, immutable source and SHA allowlist gates. Roll back only this additive presentation/test/documentation change.
