# MFX v1 — source-native SHA forensic custody without additional Drive/API calls

Checkpoint: 2026-11-13 ICT. Signal-first, Cloud-only, still NO_SIGNAL.

## Real evidence before the change

The user's approved private Google Drive source-read workflow
[#43269657301](https://github.com/ngluonghoa/MFX/actions/runs/43269657301)
PASSED 47 M5, 9 H4 and 2 D1 immutable SHA pairs. That verified archived
bytes and exact M5 root, not publisher first-known, data rights or signals.

Latest existing scheduled jobs on 2026-11-13:
- Native writer [#43357324770](https://github.com/ngluonghoa/MFX/actions/runs/43357324770):
  the original strict P0.59 `P059_SOURCE_NATIVE_REVISION_QUARANTINE`
  stopped execution. PR #144's redacted metadata reported ONE SHA changed,
  15 unchanged, zero missing **D1 (1day)** overlap labels, the changed
  label being **2026-11-11**. New source provenance types were
  `DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT`. It did not establish numeric
  price changes because old raw SHA-only index alone has no OHLC.
- Native H4+D1 read-only full SHA audit
  [#43359463766](https://github.com/ngluonghoa/MFX/actions/runs/43359463766)
  PASSED archived native pairs, but H4 lagged 3 eligible 4h calendar slots,
  D1 1 calendar day. SHA integrity of stored cache is NOT proof of freshness.
- M5 scheduled writer
  [#43355112958](https://github.com/ngluonghoa/MFX/actions/runs/43355112958)
  committed one additional 12-bar M5 hourly batch. Its separate hourly
  cadence does not make fresh M5/M15 intrahour candles.

## What the new forensic code DOES

Wrap ONLY the existing call to `audit_native_archive` in a read-through
observer with **list_names** and **read**. The observer delegates every exact
original call unchanged and retains only the latest **16** native archived
raw rows in memory. The original immutable archive auditor still validates
ALL stored manifest/chunk names, SHA, parent chain and source provenance.
Only AFTER it returns successfully, the observer cross-checks the 16 raw
typed bars by SHA, ordered label and exact symbol/interval against the last
manifest's recent SHA index. No extra Google Drive listing, media GET, new
Twelve Data request or archive mutation.

When the original P0.59 writer, on its existing budgeted provider response,
raises `P059_SOURCE_NATIVE_REVISION_QUARANTINE` or
`P059_SOURCE_MISSING_SHA_OVERLAP`, it now compares archived, fully
SHA-verified raw overlap rows with the already received fresh native batch,
in memory. The diagnostic returns counts only:

- **numeric_ohlc_changed_count**: at least one Decimal numeric OHLC
  actually differs between stored and refetched bars, even if metadata or
  string formatting also changed
- **equal_numeric_text_only_count**: equal Decimal numeric OHLC but differing
  raw price-string formatting
- **equal_numeric_metadata_only_count**: equal numeric and raw OHLC strings,
  differing non-price provenance / metadata
- **equal_numeric_text_and_metadata_count**: equal Decimal numeric OHLC,
  both formatting and non-price provenance differ

The original PR #144 changed/missing/unchanged label counts and the first
and last changed/missing source timestamp labels are preserved.
No raw OHLC, monetary values, old/new raw source SHA, credential, file name,
Drive object IDs or refresh token is written to GitHub logs.

For **true numeric changes**, this proves only that the stored, SHA-verified
numeric OHLC differs from the new provider envelope in this particular
existing request. It does NOT prove *why* Twelve Data changed it or authorize
an historical source restatement. For **metadata/format-only changes**, it
does NOT authorize a normalization rule or silently rehash immutable bars.
Either outcome remains `NATIVE_SOURCE_SHA_QUARANTINE_UNRESOLVED_NO_SIGNAL`.

The original `validate_incremental_source` exception is **ALWAYS
re-raised**, even if the helper fails or cannot prove a cause. In the latter
case only a fixed redacted marker appears. ZERO extra provider calls, usage
calls, Google Drive GETs, Google Drive writes, new scheduled workflows,
source-object replacement, publisher claims, broker orders or BUY/SELL.

## Risk guards and next evidence

- Wrapper exposes no `put_if_absent`/HTTP-write method, changes no
  `NativeArchiveState` schema, and does not intercept or mutate writer's
  actual commit store. Existing GitHub concurrency and P0.59/P0.64 guards
  remain intact.
- If archive SHA audit fails, source row attestation fails, SHA-index labels
  disagree, a label is duplicated, source scope differs, a Decimal is
  non-finite, or a classification count contradicts the existing diagnostic,
  the helper fails closed without changing the original quarantine.
- 35 hermetic tests cover actual native archive auditor read parity, bounded
  16-bar witness, H4/D1 cases, the exact November 11 D1 label as a synthetic
  source fixture, source numeric vs formatting vs provenance distinctions,
  tampering, metadata leaks and original quarantine propagation.
- These are **synthetic** fixture QA only; neither the original 2026-11-11
  D1 OHLC nor its forensic category has been confirmed by a later live job
  as of this checkpoint. Its first future actual P059 diagnostic will
  supply this information within the existing writer cadence, without
  additional fetching or any source rewrite.

NEXT: inspect the NEXT existing H4/D1 scheduled writer log for the
`MFX_P059_NATIVE_OVERLAP_FORENSICS_NO_DRIVE_WRITE` marker; compare numeric
/ price-string / metadata counts with the actual indexed 2026-11-11 D1
source before designing a separately reviewed source-correction,
revision-policy or quarantine-release process. Never automatically replace
previously SHA-sealed chunks or restart a paused writer by bypassing SHA.

Independent signal blockers remain: decision-time live M5/M15 freshness
under hourly M5 capture; account licence and retention; publisher first-known,
source owner 0/36 B2/S2 numeric approval and other 14 numeric entry models,
BID/ASK cost, SL/TP and net R:R, historical as-of / OOS backtesting.
Project is Cloud-only GitHub+Drive, no Mac/MOCHI/local, no broker and
no ChatGPT recurring engineering automation.
