# MFX 1.0 — Optional manual private-Drive GET-only six-timeframe probe

Date: 2026-11-12 ICT. Owner-approved signal-first release path Issue #138.
This PR adds an **OFF-BY-DEFAULT MANUAL** cloud integration capability after
PR #141. Not an executed authenticated real Drive read or proof of data rights.

## New components

- `tools/run_mfx_v1_manual_drive_six_tf.py`: strict read-only adapter uses
  existing GitHub OAuth token/config and app-created MFX Cache folder IDs.
  The actual Drive transport is a narrow `GetOnlyDriveSession` permitting only
  `GET https://www.googleapis.com/drive/v3/files` and exact media-file GET,
  with approved existing folder/prefix-only list queries. No `post`, `put`,
  `patch`, `delete`, generic HTTP `request` or Twelve Data endpoint is
  exposed. The outer source stores export only `list_names` and `read`.
- `mfx_research/six_tf_sealed_archive_consumer.py` remains unchanged.
  It uses full SHA/audited original root + 31-pair M5 checkpoint and existing
  P0.55 native H4/D1 full source SHA, followed by the strict causal six-TF
  CLOSED-context (M5/M15/M30/H1/H4 native/Sydney local D1).
- `.github/workflows/mfx-v1-manual-drive-six-tf-readonly.yml` registers only
  `workflow_dispatch`, **no push, schedule or cron**. Main-only,
  `contents: read`, same cooperative `mfx-twelvedata-private-cache`
  concurrency group, separate owner repository variable
  `MFX_V1_SIX_TF_MANUAL_READONLY_APPROVED=true` (off unless explicitly set),
  exact manual choice `READ_ONLY_NO_SIGNAL`, and all three already
  established M5/V2/native read-data gates must be true. No changes to
  existing hourly source writer, audit schedules, Drive objects, secrets,
  repository security settings or other projects.
- `tests/test_mfx_v1_manual_drive_six_tf_readonly.py`: 30 hermetic
  negative/positive tests enforce manual gates, blocked vendor host,
  blocked arbitrary URL/method, allowed fixed query/folders, no writer
  capabilities, output redaction, denied unauthorized run and workflow
  non-scheduling contract. No real external connection from CI.

## Operator and trust model

This is a prepared capability, NOT enabled or automatically executed.
An owner may later separately authorize a single manual execution by
setting the repository variable and choosing the explicit workflow input.
Never enable by changing production ingestion variables. Until owner
authorization, new workflow job is skipped; a denied direct CLI run exits
without loading OAuth credentials or making network calls.

At a successful manual run GitHub Actions would use existing authenticated
Google OAuth, read existing M5/H4/D1 JSON objects, validate their bounded
SHA/parent chain and source-vs-derived six-frame causal research input and
print **ONLY** current UTC as-of, available/stale frame names, counts,
three SHA tips, read call count and unverified safety flags. It prints
NO candle OHLC, file IDs, OAuth tokens, broker details or trade alerts.
Failure catches exceptions and emits a fixed nonzero fail-closed marker.
Actual OAuth GET is not an independent externally timestamped
first-known witness, provider publisher signature, price permission or
license approval. Google Drive storage may be mutable to a different
principal, and a SHA chain is not proof of independent antirollback.

The current source reader deliberately supports full bounded M5 archive
up to 256 manifests. If the archive later exceeds that bound,
the manual run must FAIL closed; rolling/older-chunk requalification is a
separate review task. The hourly M5 writer means a normal manual
wall-clock read can find the most recent closed five-minute bar stale;
the tool MUST print NO_SIGNAL/missing reason rather than backdate a
"current" signal. The existing H4/D1 native calendars and latest
session thresholds continue to apply.

## QA and release conditions

PR/head and independent protected-main push CI must separately pass
Python 3.11 and Python 3.12, frozen Forex 102 baseline, static/security
and wheel parity. The 11 SOURCE_LOCKED original Docs remain unchanged,
MFX effective 22 design zones remain 8+8 entry and 6 nonentry,
no numerical strategy approval from this work. B2/S2 0/36 external
numeric owner approvals remain OPEN and 14 other entries unqualified.
No BID/ASK, broker, actual SL/TP, net R:R, OOS or verified BUY/SELL
authorization. The release target 10 Dec is conditional.

NEXT after this PR: with separate owner authorization actually trigger
one manual GET-only workflow and verify job logs contain the expected
redacted success receipt OR a precise fail-closed reason; record run ID,
head SHA, observed dates and chain counts in canonical Drive Handoff/QA.
Do not infer real run status from synthetic PR tests. Then numeric source
authority, rights and historical OOS before any signal publication.
