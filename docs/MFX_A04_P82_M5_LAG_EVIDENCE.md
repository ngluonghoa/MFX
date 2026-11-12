# A04/P0.82 — M5 lag evidence classifier (research only)

Scope: one caller-supplied historical M5 tail audit receipt. It cannot inspect
GitHub Actions or Google Drive, establish provider availability, prove a true
outage, validate the entire history, or authorize H4 source replacement.

The prior independent M5 tail audit reported a one-hour lag at observation
time. That observation alone does not establish an outage or missing data.
This module distinguishes a stale snapshot, the existing 135-second
publication grace, a lag observation, and tail equality. All states fail
closed for source substitution, V2 activation and broker execution.

Run targeted hermetic tests:
`python -m unittest tests.test_a04_p82_m5_lag_evidence -v`

Required next operational work: obtain a newer independent read-only M5
full-SHA audit, compare the expected closed bar at that audit's UTC time,
and review the actual runner execution/market session before classifying
an incident. Never infer the 30-H4/7-day gate from this receipt.

No runtime/workflow/Secrets/Variables, native H4/D1, source Forex 102 blobs,
frozen 11 Docs, real Drive, vendor or broker mutation in this change.

## A04/P0.83 research-only correction (proposed)

The latest-due M5 tail is now computed from the **audit observation clock**,
not the later time when an analyst reviews the receipt. A valid snapshot
reviewed up to two hours later is not falsely compared to future candles.
When the audit or expected bar falls on Saturday/Sunday UTC, the classifier
returns `SESSION_CALENDAR_UNVERIFIED_RECHECK_REQUIRED` before any tail-match
or outage interpretation. This deliberately conservative weekend guard is
**not** a verified FX holiday/session calendar; Friday close, Sunday reopen,
provider-specific pauses, DST and unexpected market halts remain unproven.
Two additional hermetic regression tests bring the targeted suite to 17.
No production audit, market feed, workflow, credential, cache or broker changes.
