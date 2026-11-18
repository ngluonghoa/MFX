# MFX P0.193 — Connect real owner-selected 18-Nov D1 to GET-only six-TF research without old-price splice

**Date:** 18 Nov 2026. **Evidence:** [native scheduled first writer 44316306054](https://github.com/ngluonghoa/MFX/actions/runs/44316306054) and [independent full SHA Drive read 44337203165](https://github.com/ngluonghoa/MFX/actions/runs/44337203165) on protected main P0.192 `460834d7098cb7878c5ae15a565ecbcbd949770e`.

The owner superseded P171 11-Nov D1 by requesting a **new source-only D1 epoch from 18-Nov local Sydney**. Real P192 root is **exactly one** 18-Nov CLOSED MID bar, with an independently SHA-read-back first manifest `64c00f878e2ebe1425d9895069e1405d39402e8dc73bb7eacd2ff226e51f09ad`. A second scheduled native writer skips with zero price API requests when no new D1/H4 slots. These facts prove source custody, **not** strategy sufficiency, account/tier rights, first-known publication or any actionable trade.

## Technical ownership split

- **Prior record unchanged:** original frozen 102 Forex Git blobs and 11 SOURCE_LOCKED docs, historical V1 native D1, P169 quarantine and P171 11-Nov epoch remain SHA-audited evidence. P174 historical P171 reader/composed pre-incident seam is retained for **offline archival compatibility tests**; it is no longer selected in the actual manual GET-only research adapter.
- **New P193 real root-pinned reader:** module `mfx_research/p193_owner_nov18_active_d1_reader.py` audits **every** P192 manifest+chunk pair, parent chain, raw SHA, root identity pinned from actual writer+independent readonly audit, immutable original V1 root binding, observed source time <= research as-of and closed Sydney-local D1 date. Only labels from 18 Nov are reconstructed. No V1 or P171 OHLC is ever included.
- **Six-TF research integration:** optional `owner_nov18_d1_epoch_store` to existing `consume_sealed_archives_for_six_tf` selects only P192; P171 and P192 may **not** be supplied simultaneously, and source fixture pins remain rejected in real mode. The old V1 manifest is still audited for origin, but its bars NEVER enter P192 research. Source receipt reports P192 counts and no pre-cutoff seam.
- **Actual existing OAuth GET-only manual adapter:** `private_get_only_probe` uses `PrivateD1Nov18Store` with the previously pinned read-only Drive proxy; no vendor requests, no new Drive permissions or schedule. The P171 historical prefix stays read-only allowlisted for source-origin checks; no prior-epoch source is selected as active.
- **One candle is not an approved trend:** private research may compute on physically present sealed OHLC with strict `NO_SIGNAL/UNVERIFIED` and research-only pivot/calendar masks. D1 cannot have a right-closed 2/2 pivot from one candle; original B2/S2 numeric rules **0/36**; publisher-first-known, account-source storage/derived rights, BID/ASK net SL/TP/R:R and untouched OOS remain unapproved.
- **No synthetic source-root promotion:** tests use test-scoped monkeypatches of anchor SHA to exercise synthetic data; production module pins the exact independently witnessed immutable real P192 root.

## QA and rollback

Full exact-head CI Python3.11/3.12 all tests, original Forex golden, strict source-delta SHA allowlist, privacy/security and cross-Python wheel parity; protected squash-only PR then independent protected-main CI. Do not claim real six-TF live acceptance without a real manually dispatched read-only integrated run and source permissions. Rollback only via governed PR; preserve P192 data, old source evidence and hourly native writers. No broker activity or auto signals.
