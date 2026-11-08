# M2/P0.6 — Synthetic entitlement-event invalidation and atomic recovery failure paths

**Engineering scope:** reference-only, non-secret metadata fixtures. This is **not** licensed FX data storage or operational cache recovery. The latest approved business design remains DEC-FX-020 / Master Spec v0.9 §24; 18 labels, four states per side, FX-B9 research-only and the 20-pair five-minute objective are unchanged.

## Purpose and failure model

- `plan_synthetic_rights_cache_transition` composes the existing M2/P0.5 source/account/retention reviewer. It models an invalidation plan for **only the specified cache partition fingerprints** and dependent L1–L5 layers on observed effective revocation or expiry. Denied, unknown, future-known or stale rights block reuse rather than silently promoting a cache hit. A retroactively effective notice is recorded according to its **first-seen-by-us** time; it is not injected as knowledge into earlier simulations.
- `evaluate_synthetic_atomic_recovery` models three non-IO crash windows: existing stable commit, orphan prepared stage (ignore), and new stage with a published commit marker (validate chain before selection). Missing/torn/unknown pointer, chain gap, mismatched schema/partition, corruption, backdated generation, rollback floor or withdrawn rights return `FAIL_CLOSED`.
- Only opaque SHA-256-shaped partition IDs, simulated commit pointers and metadata-only `SyntheticGenerationManifest` objects are passed. No licensed bid/ask candles, credentials, storage paths, account numbers, remote provider calls or actual disk/database transactions are involved.
- Every plan and recovery verdict carries **false real-market-data grants**. A caller-provided marker or minimum generation floor is not an independently authenticated remote anchor and provides no protection against a compromised caller replacing the whole chain. Real crash recovery, legal hold/purge, encryption, provider licensing, host selection, account attestation and 20-pair HTTP/latency measurement remain OPEN.

## Acceptance boundary

The additional tests cover account expiry, denial, retroactive/scheduled/future-known notice semantics, selective scope, malformed metadata, staged-but-not-committed crashes, committed valid generation, corrupt parent/stage, bad marker and claimed generation rollback. Existing 349 baseline software tests must remain green on Python 3.11 and 3.12.

**No production release, no live trading, no authorization to download or retain real Forex data, no MOCHI or M15001 use.** Branch/PR review and CI are engineering evidence only. The next stage requires independent account-specific vendor rights, approved storage host/security and real bounded delta API benchmarking before any claim of operational Smart Cache speed.
