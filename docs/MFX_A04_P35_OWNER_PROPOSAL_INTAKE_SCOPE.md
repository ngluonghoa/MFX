# A04/P0.35 — Public-safe partial numeric source-owner proposal INTAKE (NOT an approval)

**State:** MFX-only GitHub+Google Drive development. The external source owner has **not supplied or independently signed** the 36 missing B2/S2 numeric conditions, and licensed live Forex + Google Drive raw quote storage rights remain unresolved. This phase creates an executable, source-anchored way to collect proposed formula decisions **without laundering unverified proposals into approved BUY/SELL signals**.

## How to prepare a review proposal

Start with [the empty public-safe template](MFX_A04_P35_PUBLIC_SAFE_OWNER_PROPOSAL_TEMPLATE.json). Its source anchors bind:
- original frozen Forex commit `7e1c1c012b1b189be5ad7b9d07756eac012a8309`;
- unchanged P0.21 source register Git blob `ef88e20271ad93c34d9d09c0cc6148f67d321929`;
- unchanged P0.34 36-row decision dossier Git blob `9b2625080705078e17572963795b41ca496481a4`;
- original source-locked Google Doc ID `10-XQxdssBTanOyTX7tSqAymRfS8XRO9YRKtjk_BsXmA`.

Each `proposal_rows` entry (optional, partial, 0–36 unique rows) must have EXACT keys:

`rule_id`, `requirement_id`, `phase`, `source_paragraph_index`, `review_intent`, `formula`, `units`, `causal_asof_notes`, `evidence_sha256`, `rationale`.

`rule_id`, `requirement_id`, `phase`, paragraph anchor must match P0.21 source exactly, one row per B2/S2 requirement. **`PROPOSE_FORMULA`** requires an explicit candidate formula, units, as-of/first-known description and a 64-character lowercase SHA256 digest of an **external separately held evidence artifact** (the digest alone does not authenticate an owner). Formula may be rejected after independent review; never copy experimental `SIM:0.5_ATR` as an approved threshold. **`SUGGEST_DEFER`** and **`SUGGEST_REJECT`** require a plain rationale but no formula/evidence. These are **suggestions**, not real owner decisions.

No `APPROVED` or `may_trade` field is accepted. The pure `mfx_research/p035_owner_proposal_intake.py` input verifier rejects unknown IDs, phase/paragraph drift, duplicated rows, stale frozen Git blobs, oversize/control strings, credentials/email/URL in public proposal text, malformed digests, extra/forged approval keys or duplicate JSON keys. A reproducible SHA256 fingerprint is calculated from the canonical ordered proposals; it **does not prove a cryptographic signature**. Proposed numeric formulas remain `FORMULA_FOR_EXTERNAL_OWNER_REVIEW`, and all **36 source approvals remain PENDING**, even when 36 proposals have been submitted.

### Secure and realistic decision process

1. Draft only **public-safe** mathematical formula/units/causal evidence *summaries* in the proposal template. Do **not** put account IDs, personal owner identities, API keys, tokens, vendor contracts, private Google Drive document URLs or quote samples in a public GitHub repository. Store private underlying evidence only in an owner-controlled Google Drive area with appropriate access; this public packet can contain a non-secret SHA256 reference.
2. Run the CI-only source review demo or call `verify_public_owner_proposals` from a controlled Cloud job to obtain exactly **36 review lines** and the missing/partial status. This is intake QA, **not** acceptance or provenance authentication.
3. External source owner decides each exact B2/S2 requirement, separately and independently verifying the controlling source paragraph/supersession, formula/units/closed UTC causal semantics, source revision/BIDASK side, positive/negative/strict-boundary tests, spread+cost+TP/SL net-R, and untouched historical OOS. Record authorization outside this public proposal protocol, using a separately governed owner approval workflow. Reject or defer when the evidence is missing.
4. Only **after** authenticated owner approvals, vendor historical/streaming Forex quote and Google Drive retention rights, and separately authorized signal delivery may future modules implement verified informational BUY/SELL. **Never** broker order submission: MFX is signal-only.

## Current baseline and QA gates

The [full P0.34 36-row source table](MFX_A04_P34_ADVERSARIAL_STRESS_AND_OWNER_DOSSIER.md) is canonical. 18 B2 + 18 S2 requirements all `SPEC_PENDING_CALIBRATION_NOT_RUN`; approved value = `null`, independently verified evidence = `null`, 14 `SIM:` examples are **not approvals**. Current MFX design 22 zones = 8 BUY entry candidates + 8 SELL entry candidates + 2 WATCH + 4 protective; only B2/S2 have experimental closed-SIM-OHLC models; original Forex source 18 remains frozen.

This change is confined to separate `mfx_research/`, public template docs, tests, hosted CI demo and exact baseline-delta SHA allowlist. [Issue #62](https://github.com/ngluonghoa/MFX/issues/62) preregistered 24 safety tests **before** implementation. Hosted Python3.11/3.12 full inherited tests, strict mypy/Ruff/source golden/security and cross-Python wheel parity required before protected squash. Independent main-push CI evidence required separately; when connector cannot verify, leave final QA pending and do not release.

**Safety invariant:** `NO_SIGNAL`, 0 source-owner-approved numeric predicates across all 16 MFX entry candidates, 36 original B2/S2 source decisions still pending, no authenticated owner approvals from public proposals, no real market provider calls or raw Drive Forex quote writes, 0 confirmed alerts/broker orders. See [Issue #45](https://github.com/ngluonghoa/MFX/issues/45) (owner evidence) and [Issue #27](https://github.com/ngluonghoa/MFX/issues/27) (vendor/storage rights).
