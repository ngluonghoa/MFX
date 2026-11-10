# A04/P0.31 — Cloud SIM research-only 22-zone label routing (NO_SIGNAL)

**Scope: running, testable source-safe presentation plumbing; not a numerical Forex detector.** The user requested continuing MFX after approving the 22-label P0.30 design, while real licensed Forex BID/ASK and Google Drive raw quote data rights are still blocked. This P0.31 module only classifies caller-supplied, explicitly synthetic metadata. An asserted `B2` or `S6` label must **never** be mistaken for proof that a market predicate has fired.

## What actually works
The separate `mfx_research/p031_sim_22_zone_router.py` calls the SHA-sealed `read_22_zone_design_manifest()` and routes any subset of the 22 approved current MFX design labels. Each immutable input requires:
- `SIM:` instrument, source calendar version, originating structural event, provider and stream IDs;
- actual typed UTC `closed_candle_end <= first_known <= retrieved <= decision` timestamps;
- approved 22-zone label, no duplicate rule for one event, no mixed providers/streams per origin and at most 256 claims.

A `ResearchZoneRow` contains a **research hint**, the exact non-entry role, and `action=NO_SIGNAL, stage=UNVERIFIED, may_publish=false, may_auto_exit=false, may_open_new_position=false`. Two roles must never be confused:
- Entry candidates (16 total): 8 `UNVERIFIED_BUY_RESEARCH_CANDIDATE` or 8 `UNVERIFIED_SELL_RESEARCH_CANDIDATE`. These are **claimed research labels**, **not** computed qualifying BUY/SELL signals, and **not** trade recommendations.
- Non-entry (6 total): `B7`/`FX-S11` WATCH, `S3`/`S8` EXIT_LONG warning only, `FX-B10`/`FX-B11` EXIT_SHORT warning only. No caller-supplied position verification is accepted here; every warning remains unverified NO_SIGNAL, even if the same event has a BUY/SELL claim.

Group by `(instrument_version, calendar_version, origin_event_id)` with one stable SHA256 research opportunity ID **independent of zone names and caller order**. Matching multiple B5/B6/B8 or S7/FX-S9/FX-S10 labels never inflates opportunity count. The same underlying event containing both entry directions is `CONFLICT_NO_SIGNAL`, and a mixed WATCH/EXIT/ENTRY remains one recorded research group with independent role lists; no arbitrary winner or pivot policy is invented. This hash is **not** a real receiver-independent persistent CAS/idempotency mechanism.

## What still does not work
No market price or candle reading in P0.31; a claim is not an independently detected structure. No real Forex stream/vendor IO/Google Drive market cache, historical/economic OOS, TP/SL, actual position/portfolio proof, alert transport, broker orders or release. The original frozen Forex 18-label `src/` catalog and its P0.17 router remain untouched; historical P0.28E 19-label overlay remains immutable and distinct from effective MFX P0.30 22-label design.

The next functional step after this safe router is **an independently calculated causal OHLC structure evidence source** and owner-approved, audited numeric gates per zone. B2/S2 retain 36 unsigned quantitative original source requirements; [Issue #45](https://github.com/ngluonghoa/MFX/issues/45) is still blocked. Vendor historical native BID/ASK and actual Drive quote retention rights remain unproven ([Issue #27](https://github.com/ngluonghoa/MFX/issues/27)). Neither the 22-label design approval nor the synthetic router implies that 16 real numeric detectors exist.

## QA/governance
[Issue #54](https://github.com/ngluonghoa/MFX/issues/54) preregistered **24** typed, scope, overlap, duplicate, causal timestamp and negative tests **before implementation**. CI runs full inherited source unit tests on Python 3.11 and 3.12 plus strict mypy/Ruff, source immutable SHA/golden checks, security and cross-Python wheel parity. No local/mac/MOCHI. Version `MFX_A04_P31_22_ZONE_SIM_RESEARCH_PRESENTATION_V1` is separate from previous module versions and approved/source manifests. Exact SHA allowlist includes only the non-`src/` module, tests, this scope doc, hosted demo and CI.

Do not declare P0.31 fully QA complete until exact PR-head PASS, squash main commit verified and independently available event=push CI PASS. If post-main CI is not accessible to connected GitHub tools, leave that gate pending rather than claiming success.
