# MFX 1.0 — verified M5 decision-time lag and source-native revision quarantine

Checkpoint: 2026-11-13 ICT. Follow-up to **real** owner-authorized
GitHub read-only OAuth run [#43269657301](https://github.com/ngluonghoa/MFX/actions/runs/43269657301).
GitHub six-TF private Drive SHA read **PASSED** (M5 47/47, H4 9/9,
D1 2/2; 221 Drive GETs, zero writes, zero vendor price calls).
But `technical_six_frame_ready=false`: M5/M15 were missing or stale at
decision time. Existing scheduled H4/D1 native writer also quarantined
some genuine provider overlap differences via
`P059_SOURCE_NATIVE_REVISION_QUARANTINE`.

## Clock arithmetic — why a one-hour archive cannot always serve M5/M15

Actual accepted run as-of: 2026-11-12T17:27:49.130710Z.
SHA-audited M5 final hourly source chunk: 16:00–17:00 UTC
(47th manifest after earlier source-locked root).
At as-of, using existing exact **15 second CLOSED grace**, the next
source-bar boundaries required by a current decision are:

| UTC frame | Last eligible CLOSED end | Last available hour end | Missing CLOSED source intervals |
|---|---|---|---:|
| M5 | 17:25 | 17:00 | 5 |
| M15 | 17:15 | 17:00 | 1 |
| M30 | 17:00 | 17:00 | 0 |
| H1 | 17:00 | 17:00 | 0 |

The last SHA-audited M5 source close was **27m49s** old at the exact
run clock. H4/D1 are provider-native and audited separately; never
substitute M5 aggregates for H4 or Sydney-local D1.

**A one-hour-only M5 polling cadence structurally cannot keep an
up-to-the-minute M5/M15 research context available all hour.**
No in-memory cache reuse, SHA verification, historical as-of label
change, trigger of an existing read-only workflow, or mathematical
derivation can manufacture a missing 17:05–17:25 M5 candle. Increasing
poll cadence, adding an approved on-demand provider refresh, obtaining
a licensed live or lower-latency stream, or changing the
signal-time-window objective would each require **separate deliberate
owner, feed/right, quota/cost and source-finality approval**.
This PR **does none** of those things. It adds true SHA-tip-relative
timestamp-only `sha_verified_source_freshness_timing` evidence to the
OFF-by-default manual read-only technical receipt: expected latest
closed end UTC for M5/M15/M30/H1, source hour, age seconds, exact
closed-slot deficits. Real source time is derived only from a fully
SHA-verified M5 manifest and source chunk, not from ambient clock guess.
Any source tip in the future, noncanonical UTC label or contradiction
between gap metadata and the existing six-TF validator fails closed.

## P0.59 native H4/D1 overlap SHA quarantine diagnostics

Already-observed hourly native writer failed on
[#43258719684](https://github.com/ngluonghoa/MFX/actions/runs/43258719684)
with `P059_SOURCE_NATIVE_REVISION_QUARANTINE`. Read-only native SHA
audit [#43261316997](https://github.com/ngluonghoa/MFX/actions/runs/43261316997)
passed existing stored H4/D1 archives; it did not waive vendor
revision quarantine or make source rights/account entitlement true.

NativeFXBar.sha256 is over its **entire** typed bar, not just OHLC.
A change in field representation (e.g. `1.100` vs `1.1000`)
or in `exchange_timezone_origin` (real `PROVIDER_META`
vs source-documented `DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT`)
can change SHA even if the actual four numeric prices have not moved.
Conversely, a SHA mismatch can indicate a real price correction.
**Old and new raw bar comparison is required to establish the cause.**
This change does NOT normalize, overwrite, reinterpret, forgive or
auto-reconcile SHA mismatches.

On the same already-budgeted native fetch performed by the existing
hourly writer, a quarantined overlap now produces one safe metadata
JSON report. Only it and only after a known original P0.59 ValueError:
interval, number of prior indexed labels, unchanged/changed/missing
SHA counts, earliest/latest changed/missing *labels*, and current
time-zone provenance origin types. No OHLC, old/new SHA, Google Drive IDs,
file names, credentials, vendor tokens or API arguments are exposed.
The exact previous ValueError is **re-raised**; the immutable Drive
archive is not mutated and no additional provider/usage/Drive read
or write request is issued by the diagnostic. If diagnostics cannot
be constructed, a fixed redacted marker is printed and the original
quarantine still propagates. Separate source-review will be required
to interpret whether the mismatch is formatting, source metadata
or numeric OHLC. This is logging, NOT repair.

## Boundary/QA

A 30-case hermetic test module checks the observed 17:27 UTC
source-close gaps, edge minutes 17:01/17:07/17:16/17:46,
strict close grace, UTC and source hour validation, no source/call
promotion, one-off manual receipt gap consistency, H4/D1 actual SHA
tampering with original P0.59 quarantine, missing overlap, same OHLC
with different formatting and source metadata provenance SHA, safe
labels-only reports and zero new I/O. No live provider read or
manual Drive re-run is claimed by these new tests.

Project retains MFX source 1:1 frozen Forex 102 Git blobs plus 11
SOURCE_LOCKED Docs, all existing production Actions workflows/schedules
and external Cache data. No Mac/MOCHI/local and no broker.

**Status remains:** SOURCE PRIVATE DRIVE SHA READ=PASS;
SIX-TF DECISION-TIME FRESHNESS=NOT READY;
B2/S2 numeric source-owner approvals 0/36 plus other 14 entry rules,
licence/retention and first-known, BID/ASK/spread, SL/TP/net R:R and
out-of-sample = NOT APPROVED; BUY/SELL remains `NO_SIGNAL`.
