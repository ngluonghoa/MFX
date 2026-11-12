# A04/P0.95 — owner-separated provider calendar evidence intake (OFFLINE; never GO)

Engineering checkpoint, 2026-11-12 UTC. Add an **offline intake review packet**, not signed proof, vendor licensing approval, production authentication, or changes to Forex M5/H4/D1 collection. Cloud-only GitHub + Google Drive.

## Governance / source research

Twelve Data's official [Forex API v2 support](https://support.twelvedata.com/en/articles/12520817-forex-api-v2) describes 24/7 service availability incl weekends and holidays and aggregated candlesticks, but does **not** provide an authenticated source-issued list of exact missing EUR/USD 5min candle slots or the account's actual feed version. The vendor notes data access depends on subscription and redistribution needs a separate agreement. See [commercial and personal usage](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage) and [Terms](https://twelvedata.com/terms). These pages are public claims, not an account-specific grant; an externally verified licence/caching term remains a distinct unmet gate.

This design deliberately does not assume the vendor publishes a signed machine-readable FX session calendar, nor fabricate any vendor cryptographic public key or downloadable artifact. In P0.94, a matching SHA covers caller-supplied content bytes only and P0.93 distinguishes public data-service availability from broker/venue schedules. Neither proves publisher signing, real feed subscription, specific closure windows, or licence permission.

## Proposed intake workflow (human/externally authorized, not executed)

1. **Submitter** proposes immutable P0.94 candidate receipt, exact EUR/USD M5 UTC MID scope, exact H4 gap labels, and *claimed* Five SHA256 artifacts (issuer statement, signing key, detached signature, account feed mapping, licensing conditions). SHA values are untrusted placeholders until separately verified against actual evidence.
2. **Custodian** would record original artifact bytes, source, date, access authority and digest in an independently controlled append-only/witnessed archive; a same-person self-asserted parent hash is not external monotonic custody.
3. **Security reviewer** would independently establish the vendor's real signing key out of band and verify actual signature bytes (not just their SHA); no public vendor key or signed exact M5 calendar was established here.
4. **Data rights reviewer** would obtain an actual subscription-specific terms/rights statement (including caching and permitted usage) from the publisher; no account entitlement inferred from public documentation.
5. **Owner** separately decides whether a research review should continue. Production H4 cutover, automatic weekend gap waiver, trading orders and numerical BUY/SELL are all explicitly outside this workflow.

Use five **distinct role IDs** and immutable exact input types to detect claimed separation failures. The tool has no identity directory, auth grant, signing key or signature bytes and therefore **cannot authenticate those role IDs**. No role input can approve real production.

## Offline verifier scope

New `tools/mfx_fx_calendar_owner_review.py` imports but **never modifies** P0.93/P0.94. It accepts an existing P0.94 `SnapshotCustodyReceipt` from synthetic fixtures plus a claimed provider review packet and reviewer separation. Rejects source/product/route/version drift, improper approval request, duplicate/reused claimed evidence SHA, future/replayed/expired evidence, stale collection beyond seven days, wrong exact UTC 4-hour windows, wrong H4 gap ordering or scope, missing/colliding role IDs and unsupported public-redistribution permission claims.

The receipt reports `P095_COMPLETE_UNVERIFIED_REVIEW_PACKET_NO_PRODUCTION_AUTHORITY` for a structurally complete packet, **not** authenticity. P0.94 only carries aggregate gap counts and does not cryptographically bind each later gap label; explicitly report `exact_gap_labels_proven_by_snapshot_sha=false` even when counts match. Claimed key/signature/account/license artifacts are never verified; all issuer/roles/account/rights/witness/calendar/owner-GO fields remain FALSE. Zero provider calls, zero Google Drive writes, no broker, no native H4 request reduction/source replacement or Sydney D1 change. The new `tests/test_a04_p95_fx_calendar_owner_review.py` contains 69 hermetic negative/positive tests.

## Unchanged evidence and NEXT

The last independent real P0.66 read-only audit is **P0.91** GitHub #43138482666 attempt5: 41/41 M5 SHA, 492 fully closed M5 bars through 2026-11-12T10:00Z, head `2676a0f5695c5639fb5a9d2800debb6d40cb3c0343e9d482144b3e3472f42ea1`; native H4 SHA 8/8, nine complete exact M5/H4 comparisons, not >=30 windows/7 real days. P0.95 makes no new SHA assertion and does not re-run production workflows, price API or private Google Drive cache audit. Frozen Forex 102 Git blobs and 11 source-locked Docs remain unchanged, same for original numeric FX B2/S2 0/36 owner signoffs, live witness/CAS and broker.

**NEXT P0.96:** design an exact-label-content-binding and externally witnessed custody review schema (untrusted-proposal SHA over exact gap labels, externally controlled witness separate); do not implement fake vendor signatures, start a new provider polling job, waive missing sessions or change H4/D1 source. Explicit separate owner GO remains required after verified 30 full H4 windows across >=7 real days, legitimate session gaps, rights, source and availability.
