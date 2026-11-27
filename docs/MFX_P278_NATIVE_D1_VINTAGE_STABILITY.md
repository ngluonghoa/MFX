# P278 — native D1 whole-vintage revision and ordinal capacity study

Use the existing P220 verified native snapshot history. At each distinct
archive creation instant select P254's latest runner-observed whole vintage
among those actually visible. A later-arriving older observation does not
replace a newer visible observation. Count overlapping row SHA changes,
additions, removals and ordinal 1/1 and 2/2 shared strict pivot capacity.
Do not concatenate vintage rows or claim qualified trading-day adjacency,
publisher first-known, market direction or historical OOS.

Independent direct evidence before implementation: 17/17 P209 private
records match identity, record and row SHA; 124 adjacent creation-ordered
overlap comparisons, 12 changes, four additions, zero shrinking snapshots;
zero of 17 can supply two highs and lows under the preliminary ordinal
capacity check. P278 uses ACTIVE selection clocks, which may differ from
simple creation order. No raw price or direction outputs, no cache writes,
vendor calls/outreach, new schedule, or canonical D1 changes.
