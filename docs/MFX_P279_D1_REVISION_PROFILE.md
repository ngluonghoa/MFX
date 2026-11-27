# P279 — native D1 revision concentration and observed age

Existing 17 SHA-verified private P209 snapshots from P277/P278: 124 overlapping
comparisons, 12 changes on the preceding snapshot's terminal label, none on older
labels, three distinct revised labels. Numeric Open/High/Low/Close changes
0/3/0/12; changes need not be mutually exclusive. Runner observation lag from
the label's next Sydney civil midnight: 1 in [0,3), 6 in [3,6), 5 in [6,12)
hours. This is not market-session closure or publisher first-known. Small,
dependent sample and no proof of a 12-hour maturity policy.

Add aggregate counts to P278 active whole-vintage transitions without fetching
new data, selecting a maturity threshold, altering selection, stitching,
overwriting canonical D1, producing directions, or promoting source authority.
Exact SHA changes without numeric OHLC change are separately counted. Prior
terminal vs older overlap denominators and distinct revised labels are kept
separate. ZoneInfo converts Sydney civil midnight including DST. Only masked
counts/booleans in existing public summary. Existing read-only workflow and
production/cache schedule unchanged. NO_SIGNAL.
