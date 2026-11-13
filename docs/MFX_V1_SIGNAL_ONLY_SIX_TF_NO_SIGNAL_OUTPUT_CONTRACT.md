# MFX v1: six-timeframe signal-only output contract — offline NO_SIGNAL

Date: 2026-11-13 ICT. Parent [Issue #138](https://github.com/ngluonghoa/MFX/issues/138). Source revision HOLD [Issue #147](https://github.com/ngluonghoa/MFX/issues/147).

## What is implemented

New MFX-only pure function `build_signal_only_research_response` accepts the existing typed `SealedArchiveSixTFReceipt` research witness produced by P0.141. It does not call that witness's Google Drive readers itself, invoke providers, mutate cache, create signals, or talk to a broker.

It constructs an immutable JSON-compatible typed presentation that keeps the six technical frames (M5, M15, M30, H1, native H4 and native Sydney-local D1), missing/stale frames, SHA tip fingerprints, and distinct deterministic block reasons in one `NO_SIGNAL / UNVERIFIED` object. Entry, stop-loss, take-profit, net R:R, zone and independent publisher first-known timestamps remain **null**, not fabricated from composite MID. The fingerprint of caller-supplied source evidence is **not** a signature or independently authenticated publisher statement. The result is an intentionally research-only, not a production API endpoint.

Guard conditions require the exact existing typed versions of the six-frame and sealed archive receipts, known source symbol/provider/MID, exact UTC as-of, ordered nonduplicated frame identities, internally consistent completeness, a nonprivileged input, 64-character hexadecimal hashes, and internally consistent M5 full/rolling raw SHA claims. Rolling old raw chunks explicitly remain **not reread**. Rewriting an approval bit in a copied/rehashed input causes a fail-closed validation error; this is a schema guard, **not** a cryptographic proof against full source fabrication.

## Critical boundaries

1. This PR does **not** implement numerical original Forex B2/S2 conditions: owner-approved rules remain 0/36 and other entry family numeric predicates remain unapproved. Never emit verified BUY/SELL or import SIM pilot thresholds.
2. It does **not** prove feed subscription/storage rights, signed first-known/publisher revisions, account-specific BID/ASK spread, SL/TP, net R:R, deterministic OOS or economic profitability.
3. Source archives H4/D1 remain under the original strict P059 SHA quarantine, including the observed real D1 2026-11-11 numeric difference. Issue #147 is deliberately OPEN; no source correction write/auto-restatement or new Drive namespace is enabled.
4. The known hourly M5 writer cannot guarantee intra-hour M5/M15 freshness. An actually missing frame is reported missing; no artificial M5 candle or D1 UTC midnight is invented. No workflow, GitHub variable, cache cadence, Twelve Data price request or market-data snapshot is changed.
5. Pure tests construct hermetic synthetic typed receipts. They prove schema behavior only, **not** authenticated live Drive execution, actual pricing quality, historical OOS or entitlement. No Mac/MOCHI/local compute, no cross-project source changes, no broker activity.

## QA and rollback

Run exact PR-hosted GitHub Cloud Actions full Python 3.11 and 3.12 suites, frozen Forex 102-blob gate, static/security checks and cross-Python wheel parity. Merge only with successful green CI and independently verify the protected main-push run before calling this offline contract accepted.

Rollback only the new MFX-only source, hermetic test and this document, plus their SHA-pinned allowlist entries. Never touch prior sealed archive, source-locked 11 Docs, source revision issue, schedules, vendor quotas, credentials or original Forex modules.

## Next release-critical work

Use this typed `NO_SIGNAL` response shell to connect future **approved original source numerical detector** outputs and governed actual-as-of evidence. Do not enable BUY/SELL until explicit source-owner numeric/rights, execution-cost, as-of and OOS gates independently PASS. This PR cannot resolve those owner gates.
