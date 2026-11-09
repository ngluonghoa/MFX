# A04/P0.13 — Evidence intake attestation checklist and negative receipts

## Scope / immutable upstream

Pure **synthetic attestation schema and evidence-required stop gate**, no actual provider or legal terms verification. Frozen Forex commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`; initial MFX byte-preserving 102 blobs `6ee5e7c07baf4ea8f06a28889175808ea53c2316`; P0.12 synthetic case baseline Git blob `b28a79961c20921af0f5984f7735f22f4dd03bc1`. P0.11 seven source functions and 58 unverified field obligations remain; P0.12 32 synthetic quote/clock/rights negative cases remain.

## P0.13 deliverable

Define exact consent/evidence intake schema with seven independently checked rights dimensions: API read, historical read, Google Drive cloud storage, retention, redistribution, derived use, replay; eight provider capability dimensions: native BID/ASK, candle availability, historical BID/ASK, first-known timestamps, revisions, DST/calendar, product-to-broker alignment, quotas. Each dimension must have actual **provider/product/account/license-holder-specific** terms or independently trusted technical evidence plus effective/expiry dates, disclosure/read/store rights, and independent reviewer/owner approval. No private token, account identifier or vendor document is stored in these public repository fixtures.

**46 strictly synthetic denial cases**, with no real URL or credential, cover false entitlement, false signed vendor evidence, rights denial, historical and retention rights, missing or future-known documents, expired licensing, capability claims, token or account claims, missing/extra fields, unauthorized cloud budgets, real feed/caching/runtime/orders. A structurally complete unverified synthetic input yields `EXTERNAL_VENDOR_EVIDENCE_REQUIRED`, not `APPROVED`. Every receipt explicitly sets `may_read_vendor=false`, `may_write_drive_cache=false`, `may_trade=false`.

## Evidence still missing after successful CI

- SIGNED_VENDOR_PRODUCT_SPECIFIC_TERMS_AND_LICENSE_HOLDER
- API_READ_HISTORY_STORAGE_DRIVE_RETENTION_REPLAY_DERIVATIVE_RIGHTS
- NATIVE_BID_ASK_BROKER_PRODUCT_SIDE_PROOF
- VERIFIABLE_FIRST_KNOWN_CLOSED_BAR_REVISION_DST_CALENDAR
- SUPPORTED_TF_RATE_LIMIT_COST_AND_CLOUD_BUDGET
- TRUSTED_EVIDENCE_ORIGIN_DIGEST_EFFECTIVE_DATE_AND_MANUAL_REVIEW

This is **a design contract for future independent review, not evidence that any entitlement or API capacity has been verified**. Real provider credentials/terms should be reviewed through a separately approved secure workflow; never commit secrets, personal license documents or real provider data to public GitHub. Any external call, Google Drive data caching, paid execution, trading adapter or source change requires explicit owner approval and security/licensing validation. CI remains original Forex 50 golden, 34 wrapper, 28 P0.8 STOP, P0.9–P0.12, 17 mutant, 80 feedback, coverage floor, mypy strict 30 original modules, security audit and wheel parity. No `src/` changes, GitHub and Google Drive Cloud-only.
