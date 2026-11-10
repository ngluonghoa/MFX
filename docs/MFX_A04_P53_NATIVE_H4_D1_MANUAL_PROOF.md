# MFX A04/P0.53 — Manual-only native H4 / D1 metadata proof

Status: **STAGED: no actual vendor response or Google Drive H4/D1 cache accepted yet.**

## Why this probe

P0.52 established strict native Forex H4 and D1 parsing without network access. The vendor supports both `4h` and `1day` intervals, but D1 ignores `timezone=UTC` and uses exchange-local dates (Twelve Data public docs). The next step is to prove an actual authenticated GitHub Cloud REST payload matches these contracts. **Do not interpret this probe as an approved live H4/D1 Cache implementation.**

## Workflow

- `.github/workflows/mfx-native-htf-manual-probe.yml`: manual `workflow_dispatch` only, no cron, same `mfx-twelvedata-private-cache` concurrency group as V2 hourly M5 writer.
- Requires existing repository gates `MFX_REAL_CACHE_ENABLED=true` and `MFX_V2_BATCH_CACHE_ACCEPTED=true`; no new opt-in variable. The existing EUR/USD M5 job remains unchanged.
- Only `MFX_TWELVE_DATA_API_KEY` Secret and nonsecret local cap are provided. **No Google Drive OAuth credentials, folder IDs, write access, or broker credentials**.
- Executes at most one `time_series` request for **EUR/USD 4h timezone=UTC** and one for **EUR/USD 1day, without any timezone parameter**, plus read-only vendor quota checks. Both requests are bounded to 120 responses.
- Preflight must leave headroom for both price requests given observed minute-plan limit and cap; check quota again before second call. Usage/response failures terminate safely and must not reveal query URLs containing the API key.
- For H4, validates 4-hour closed candles and labels UTC; for D1, validates exchange-local dates, IANA timezone, and excludes current local day. Unknown source/meta/timezone fails closed.
- The only output is sanitized metadata: source interval, timezone, first/last native labels, closed counts, excluded counts and a digest of deterministic per-bar SHA values. **Never log raw price values**. No Drive file is created.
- Successful proof marker: `MFX_A04_P53_NATIVE_H4_D1_METADATA_ONLY_TWO_REQUESTS_PASS`. GitHub job Success without this marker is NOT acceptance.
- Quota guard may result in `MFX_A04_P53_NATIVE_PROBE_QUOTA_NO_PRICE_REQUESTS`; this is not a validated native TF receipt.

## Safety/limits

- The probe can consume up to two market time-series API requests; actual vendor credits depend on provider policy. It does not attempt market execution or turn MID data into tradable BID/ASK data.
- This only proves EUR/USD H4/D1 metadata and complete bar parsing at one point in time, **not** multiple instruments, long-term cache persistence, missed-hour recovery, D1 UTC calendar, or source numeric BUY/SELL correctness.
- D1 is stored with `EXCHANGE_LOCAL_SESSION_DATE`, not `start_utc`.
- Vendor data retention terms have not been independently verified. No credential/token changes or alteration to existing MFX cache is made.

## Acceptance

1. GitHub PR Python 3.11+3.12 complete 15 hermetic tests and source-parity integrity; cross-Python build parity PASS.
2. Merge into `main`, confirm push CI PASS.
3. Open `https://github.com/ngluonghoa/MFX/actions/workflows/mfx-native-htf-manual-probe.yml` and run the workflow **manually** on `main` when ready; do not run during quota contention.
4. Review actual Actions log for the exact PASS marker and native `exchange_timezone`, time reference and counts for **both** `4h` and `1day`, with zero Drive writes and broker orders.
5. Only after authenticated real proof build a *separate staged* per-pair/TF immutable H4/D1 Drive writer with new dedicated activation gates and a read-only SHA audit. Do not activate a new hourly H4/D1 schedule just because this metadata probe passes.
