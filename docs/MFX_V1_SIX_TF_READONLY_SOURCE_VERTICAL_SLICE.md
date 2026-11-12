# MFX 1.0 signal-first — first executable six-timeframe read-only source slice

Checkpoint: 2026-11-12, *first code milestone after owner-approved release-critical pivot* [Issue #138](https://github.com/ngluonghoa/MFX/issues/138), [PR #139](https://github.com/ngluonghoa/MFX/pull/139). Full original Forex102 and 11 locked Docs remain immutable.

## Delivered — actual composition, not another policy-only paper exercise

New `mfx_research/six_tf_readonly_context.py` invokes the existing functional `mfx_cache.v2_engine.validate_m5` and `derive_intraday` on already-parsed, CLOSED, UTC EUR/USD **M5 MID** `ClosedM5Bar`, and accepts independently parsed `NativeFXBatch` **H4 native** and **D1 Sydney-local**. It computes a deterministic *technical research* six-frame receipt with the latest eligible **M5, M15 (exact 3xM5), M30 (6xM5), H1 (12xM5), provider-native H4 and Sydney-calendar native D1**, per-timeframe OHLC, labels, source representation, source-specific digests and missing/stale status. These six frames now have a single usable typed **read-only analysis input contract**, not just a design diagram.

It rejects malformed/future/unsorted/gapped M5, open or unaligned native H4, same-day Sydney D1, mixed pair/side/source, forged native permissions, native type/timezone drift and partial derived windows. Requires newest M5/M15/M30/H1 windows exactly aligned and fully CLOSED at decision time, including a 15-second grace. Applies *conservative research-only* native H4 max-age eight hours and D1 Sydney local-session date max-age three days, not pretending they are independently authenticated provider session closures. Native D1 uses local date only: **never creates a synthetic UTC midnight/open/end**. Every source-evidence row is tagged `MID` and explicitly UNVERIFIED; input and row content hashes are deterministic **caller-supplied bytes fingerprints**, NOT independently verified Drive manifest/chunk SHA.

Full six-frame technical availability yields `SIX_TF_TECHNICAL_RESEARCH_READY_NO_SIGNAL`, *not* an authenticated market signal. Incomplete/stale data yields `SIX_TF_MISSING_OR_STALE_NO_SIGNAL` with exact missing frames. **Public action always `NO_SIGNAL`, stage `UNVERIFIED`**: no verified feed subscription, actual Drive custody, original Forex numeric parity, historical as-of replay, BID/ASK spread, entry/SL/TP/net-R approval, BUY/SELL authorization or broker trade. Pure code makes **zero real vendor calls, Drive writes or orders**; existing GitHub Cloud-only writer/cron/secrets/native H4/D1 remain untouched. This is the first compositional step toward a signal-only v1, not production release.

## QA

New `tests/test_mfx_v1_six_tf_readonly_context.py`: **40 hermetic tests** exercising exact six-frame composition, 3/6/12 aggregation, open/future M5/H4 protection, missing newest H1, interior M5 gap, native H4 source identity and 4h grid, Sydney-local D1 preservation, owner-safe NO_SIGNAL statuses, hash sensitivity and all zero-I/O locks. Fixtures call real existing P0.52 `parse_native_forex` with synthetic vendor envelopes; these are **not** a fresh vendor/Drive audit. Full CI on Python 3.11/3.12 plus frozen Forex102, static/security and cross-wheel must pass before merge. MFX-only additions and exact SHA manifest exceptions.

## Next release-critical vertical slice

1. Attach source-authoritative zone/phase numerical B2/S2 owner review to the now runnable six-frame source input; 36/36 obligations still pending. Preserve 22 roles and original Forex18 distinct.
2. Introduce a **read-only authenticated private Drive cache consumer** after independently verifying file manifest/chunk digest chain and source rights, then convert truly independently dated latest frames into this same contract. Do not schedule extra vendor polling.
3. Add informational entry/SL/TP/net-R once original source numeric predicates and spread/BIDASK cost evidence exist, then deterministic historical OOS replay.
4. Keep conditional Dec10 target dependent on all release gates. Do not reroute team to H4-derived substitution or fake number of completed numeric detectors.

Security: no Mac/MOCHI/local, broker execution, user-facing live signal, source code freeze break, Google Docs lock override, or automatic ChatGPT task re-enable.
