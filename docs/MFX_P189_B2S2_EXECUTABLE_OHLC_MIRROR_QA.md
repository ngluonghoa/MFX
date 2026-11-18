# MFX P0.189 — Executable B2/S2 CLOSED-OHLC metamorphic mirror QA

**Scope (18 Nov 2026):** Accelerate Nov 22 B2/S2 signal-only research MVP without weakening frozen original Forex source, owner numeric permissions, D1 publisher custody or vendor data rights.

## Why this is needed

P0.161 already generated experimental B2 BUY and S2 SELL on *different* synthetic sequences. P0.182 proved the involutive nature of qualitative phase labels on caller-provided evidence, not numerical price action. Neither proves that the actual P0.161 executable OHLC calculations are fully symmetric when the *same* closed-price series is reflected HIGH↔LOW, D1/H4 UP↔DOWN and M15 pivot HIGH↔LOW. This matters because the owner explicitly required exact B2/S2 mathematical symmetry.

## Deliverables

- New mfx_research/p189_b2s2_executable_ohlc_mirror.py — offline SYNTHETIC-only exact price reflection. For a positive price anchor A, transforms open'=2A−open, high'=2A−low, low'=2A−high, close'=2A−close, preserves original source time/provenance. Reflects D1/H4/H1/M15 plus the right-confirmed M15 pre-trigger history together. Recomputes both P0.161 numeric candidate paths for an original side and opposite side, checks BUY/SELL/NO_SIGNAL inversion, D1/H4 trend, all confirmed pivot candidate indices/prices and right-closed confirmation times, H1 simple-mean True Range, zone limits and width, confirmed micro level and 22-zone routing. Errors stop any asymmetric case. Rejects real providers, non-MID price side, open/partial/unverified bars, revised bars, invalid anchor and mismatched M15 history.
- New tests/test_mfx_p189_b2s2_closed_ohlc_mirror.py — 22 hermetic tests on both sides, three anchor choices, double-reflection identity, every series' source/time provenance, pivot and H1 zone equality, missing D1/H4 symmetric NO_SIGNAL, price translation, future-known exclusion, forged data/rights rejection, public metadata redaction, deterministic freeze and zero network/Drive/broker output.
- Output public summary never exposes private price, pivot/direction or vendor values. Only SYNTHETIC_OFFLINE_ONLY, NO_SIGNAL/UNVERIFIED, exact mirrored roles, original owner numeric 0/36, zero provider/Drive/broker permissions.

## Non-goals and independent hard gates

- These calculations are invented SIM-only synthetic candidate research. They do NOT approve 11 experimental P160/P161 numeric proposals or seven still-undefined rules from P188. Original Forex 1:1 numeric B2/S2 owner decisions remain 0/36 (#45/#62); all 102 original blobs and 11 SOURCE_LOCKED Google Docs remain unchanged.
- No authenticated point-in-time market data, licensed vendor retention/BIDASK/spread and net-R:R economics or original source-owner formula authority (#27).
- Native P171 D1 incoming SHA revision conflict remains quarantined with one changed/5 overlap and no source publisher-first-known (#180); no changes to D1 source, writer, epoch or release gates.
- Chronological untouched OOS, true quote economics and external release authority still pending (#138). No live BUY/SELL or broker order execution.
- No workflow/cron/secret/Drive folder changes; no price API calls and no Drive writes. Existing M5/H4 source cache and SHA auditors remain unchanged.

**Acceptance rule:** CI passes in Python 3.11/3.12; original Forex golden/security and crosswheel unchanged; protected PR squash-only merge plus independent post-main CI. QA parity of an unapproved synthetic draft does NOT constitute a real market signal GO.
