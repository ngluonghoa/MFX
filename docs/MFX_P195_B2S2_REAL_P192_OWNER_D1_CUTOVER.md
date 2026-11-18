# MFX P0.195 — B2/S2 real six-TF seam uses only owner P192 D1 from 18 Nov

**Decision provenance:** owner instructed on 18 Nov 2026 to ignore prior active D1 source prices and start a fresh native Sydney-local EUR/USD D1 epoch with the **18-Nov** closed candle. P192 wrote the immutable one-day source and separately SHA-audited it; P193 switched the manual six-timeframe reader, P194 independently witnessed the real P193 D1 reader on protected main. This PR fixes the **separate P187 B2/S2 vertical-slice public entrypoint**, which still exposed only `active_d1_epoch_store` (P171, now archival).

## Source-safety change

- Add `owner_nov18_d1_epoch_store` to `from_sealed_stores_b2s2_signal_only()`. Pass the store to the **existing** P193/P192 validated `consume_sealed_archives_for_six_tf()`. The adapter uses the existing independent P192 root SHA, original V1 SHA parent, complete chunk/manifest SHA, provider observed-as-of and Sydney-local D1 closed candle.
- For a **non-synthetic B2/S2 invocation**, require the P192 store; missing new epoch is a hard refusal **before** touching M5/H4/D1 archive storage. Do not fall back to P171 or original V1 D1 prices. The previously existing synthetic `fixture_pins` path remains unchanged and is not source authorization.
- Simultaneous P171 and P192 epoch stores remain forbidden by the same P193 underlying consumer. The public `B2S2SignalOnlyGate` names only the selected non-price `active_d1_source_epoch`; the new P192 no-splice invariants forbid any earlier D1 bar stitching even if a receipt is forged.
- No new quote vendor calls, Drive writes, workflow schedules, permissions, OAuth secrets, brokerage, risk limits, original Forex 102 Git blobs or SOURCE_LOCKED 11 Docs changed. One P192 D1 candle does **not** meet historical confirmed D1 pivots.

## Expected QA

Nine new hermetic adversarial tests: P192 source end-to-end into the actual B2/S2 gate, explicit epoch with masked `NO_SIGNAL` output, absent P192 hard STOP before storage reads, P171+P192 ambiguity denial, wrong P192 root SHA, tampered closed D1 chunk, source observed-after-as-of failure, forged pre-18-Nov history splice denial, no fake confirmed source BUY/SELL. Existing 17 P187 tests and 7 P193 synthetic no-splice tests remain as regressions. Require exact-head Python 3.11/3.12 full CI, source-golden SHA allowlist, wheel crosscheck, controlled squash PR and independent postmain CI.

## Important distinction

This PR tests and connects the B2/S2 **software call chain**; it is **not** proof that the operator-gated real six-TF Google Drive workflow ran. The manual `.github/workflows/mfx-v1-manual-drive-six-tf-readonly.yml` still requires explicit repository approval and `READ_ONLY_NO_SIGNAL` dispatch. No such workflow is activated, run or repurposed as cron here.

**Release status:** `NO_SIGNAL/UNVERIFIED`, original numerical source-owner approvals **0/36** (#45), real vendor BID/ASK and account tier rights (#27), provider first-known and historical #180 provenance, SL/TP/net R and independent chronological OOS (#138) remain blocked. The owner target 22-Nov is **conditional GO/NO-GO**, never an automatic verified BUY/SELL authorization.

**Rollback:** revert only P195 additions in P187 entrypoint, this test and document, plus allowlist SHA entries. Existing P192 sealed Drive source and old archives remain immutable.
