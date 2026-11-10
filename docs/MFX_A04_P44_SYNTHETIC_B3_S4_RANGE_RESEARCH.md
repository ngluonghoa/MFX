# MFX A04/P0.44 — computed B3/S4 synthetic H1/M15 range-edge rejection pilot

**Authority:** MFX-only RESEARCH_ONLY, not approved numerical Forex Trading 1:1 strategy. Issue #72, P043 P029 SHA-sealed source review; original 18-label Forex catalog and all original frozen source Docs unchanged. User goal is informational BUY/SELL signals only, no broker order integration.

## What is genuinely computed

Two new experimental patterns are generated from typed, complete, closed, chronological, SIM-only MID OHLC: B3 experimental BUY when a prior M15 sweep closes below a precomputed H1 range low and the next M15 closes back above the low/reclaim margin and prior micro high; S4 experimental SELL is the directional reverse at the precomputed upper H1 boundary and prior micro low. H1 range high/low are computed only from **last 4–24 prior H1 bars**, with one extra prior H1 close for true-range calculation. Each edge must have an explicit experimental minimum number of historical touches; the sweep/reclaim depth, touch tolerance and margins are configured through explicit SIM-only research parameters. No default Forex source threshold is invented.

The causal cutoff is the *start* of the sweep M15 bar: all historical H1 bars must be CLOSED, COMPLETE, VERIFIED, MID, contiguous, revision=1, from one explicitly SIM provider/calendar/stream, known and retrieved by that cutoff. Both subsequent M15 bars must be CLOSED/COMPLETE/VERIFIED and known/retrieved before decision; they are contiguous and the historical H1 range ends exactly at sweep start. Future-known/revised/real-source/partial bars, mixed calendars, missing H1 candles, forged source labels and unsupported strategy IDs fail closed.

**Important limitation:** this research pilot only computes an H1 range with simple repeated-touch evidence; it does not establish original source-approved H4/H1 range confirmation, causal pivot-count/lookback, B3-versus-FX-B9 overlap priority or independently calibrated thresholds. Prior H1 touches are a chosen research hypothesis, not an original Forex specification. No realistic BID/ASK, spread, fees, swap, SL/TP, OOS or approved economic performance is calculated.

## Explicit provenance and typed output

The pure computation `mfx_research/p044_sim_range_rejection.py` returns an immutable receipt with experimental BUY/SELL/NO_SIGNAL pattern, predeclared historical H1 low/high, mean true range, boundary touch counts, first-known/decision times, deterministic synthetic origin and input fingerprint, plus P031 approved 22-label role routing. `B3` routes only as UNVERIFIED BUY research group; `S4` only as UNVERIFIED SELL research group. No computed pattern => zero P031 label claims or events. All *external* actions remain `NO_SIGNAL`: numeric source-approved 0/16, B2/S2 original-owner decisions 0/36, actual confirmed alerts=0, provider calls=0, real Google Drive quote-cache writes=0, broker orders=0, release_ready=false.

27 positive/negative boundary/provenance tests under `tests/test_a04_p44_sim_range_rejection.py` and an executable GitHub CI demo `tools/run_a04_p44_sim_range_demo.py`; Python3.11/3.12 strict mypy, frozen Forex source, deterministic wheel and security CI are mandatory before merge. No `src/forex_trading/` edits, no local/Mac/MOCHI, no user account data.

## Parallel vendor read-only check: Issue #27

Twelve Data public [Forex v2 guide](https://support.twelvedata.com/en/articles/12520817-forex-api-v2) documents weighted composite pricing, MID minute updates and aggregated OHLC; it does NOT independently prove broker-specific historical BID/ASK or historical as-of revisions. Its [Terms §2.2–2.3](https://twelvedata.com/terms) limit use/storage/cache to the actual subscribed plan, permitted timeframes and rights. Its [personal/commercial support](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage) distinguishes internal individual research from distribution/commercial display. Public documents do NOT grant indefinite archival raw Forex candles on Google Drive. Until account/tier-specific written permission and reliable first-known/economic data are provided, Gate L remains BLOCKED and Gate Q remains UNVERIFIED. No price API connection, vendor contact, external storage or credentials were used in P044.

**Next work after P044:** continue independently tested synthetic research scenarios, and seek actual authenticated source-owner 36 decisions (#45) and plan-specific vendor/cache rights (#27). These are separate workstreams; completing source-negative tests does NOT resolve them.
