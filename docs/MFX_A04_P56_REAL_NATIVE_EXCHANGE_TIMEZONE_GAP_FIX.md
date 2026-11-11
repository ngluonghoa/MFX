# MFX A04/P0.56 — Missing Twelve Data native Forex exchange timezone metadata

**Status:** Code fix STAGED until PR CI + main CI and an authenticated rerun of the manual real H4/D1 writer. **Do not claim live H4/D1 Cache before real Drive Chunk + Manifest SHA readback.**

## Evidence

- Owner dispatched manual native EUR/USD H4/D1 cache writer twice: GitHub Actions [#42958134955](https://github.com/ngluonghoa/MFX/actions/runs/42958134955) and [#42958219633](https://github.com/ngluonghoa/MFX/actions/runs/42958219633). Both returned `ValueError: P052_EXCHANGE_TIMEZONE_REQUIRED` at `parse_native_forex` during the **first** provider-native H4 source probe, **before Drive authentication or writes**.
- Independent Google Drive folder metadata shows 9 existing EUR/USD M5 V2 Chunks and 9 Manifests, **zero H4/D1 native** objects as of 2026-11-11 04:17 UTC. Latest hourly M5 writer [#42956128454](https://github.com/ngluonghoa/MFX/actions/runs/42956128454) committed 2026-11-11 02:00 UTC with 12 closed M5; M5 is not regressed by P0.56.
- Twelve Data's published [Timezones](https://support.twelvedata.com/en/articles/5745849-timezones) specifies **Australia/Sydney as Forex's default exchange timezone**. Its [API documentation](https://twelvedata.com/docs/mcp) specifies the `timezone` query parameter is applicable only intraday; D1 ignores it and returns exchange-local session dates.

## Minimal narrowly approved source fallback

- `mfx_cache/native_fx_htf.py` first accepts an explicit valid `meta.exchange_timezone` from the provider, with source flag `PROVIDER_META`.
- **Only for a correctly typed EUR/USD Forex response**, when the provider field `exchange_timezone` is omitted, `null` or empty string, the parser uses **Australia/Sydney** with the distinct origin `DOCUMENTED_TWELVE_DATA_FOREX_DEFAULT`. This is the *publicly documented provider default*, not a claimed value returned in metadata.
- An explicitly present but invalid/non-IANA zone still fails. A missing exchange zone for any other pair still fails: no silent global assumption.
- Each source-native H4 or D1 bar carries `exchange_timezone_origin`, included in its canonical SHA256 and sealed H4/D1 Chunk object, so later readback distinguishes documented-default from provider-supplied data. Native archive validation enforces the allowed origin and permits documented fallback only for EUR/USD Australia/Sydney.
- H4 request still explicitly uses `timezone=UTC`, and its bar time axis remains `UTC_INTRADAY_OPEN`. Its exchange-default zone is provenance metadata, **not a conversion of H4 UTC labels**.
- D1 request still omits the `timezone` argument, keeps dates as `EXCHANGE_LOCAL_SESSION_DATE`, and never invents a UTC D1 open timestamp. The most recent exchange-local date remains incomplete and excluded.
- The P0.53 source metadata proof and P0.55 actual write receipt emit `timezone_origin` / `timezone_origin_by_interval`. No raw prices or API keys are logged.

## QA and safety

- P0.52 regression tests include explicit missing-zone EUR/USD H4/D1, verified default-origin labels, no fallback for GBP/USD and invalid explicit zone rejection.
- P0.54 tests verify origin changes the SHA-256 sealed object and rejects unrecognized or cross-pair documented-default tags.
- P0.55 mocked OAuth Drive tests verify documented fallback origin survives content-addressed Chunk creation, reading and full-chain audit; invalid origin aborts with zero write.
- Existing M5 writer and its Cron/Audit, H4/D1 activation variables, provider quotas and GitHub concurrency group remain unchanged. No Mac/MOCHI/local, no numeric signal promotion, no broker, no HOT activation. No new automatic H4/D1 schedule.
- Metadata default sourcing does not independently validate commercial market-data retention rights. The owner has directed private Google Drive Cache without additional vendor contact.

## Remaining real acceptance

1. Protected PR CI Python 3.11 + 3.12 + wheel parity + source-delta manifest PASS, then main-push CI PASS.
2. Since the owner already set the native writer activation flag, **do not ask for the same settings again**. Re-run the manual [P0.55 native H4+D1 writer](https://github.com/ngluonghoa/MFX/actions/workflows/mfx-native-htf-drive-commit.yml) on **main** after this fix is merged. The script independently validates both native REST responses before writing.
3. If another metadata mismatch arises, fix the verified actual field; never invent values. Confirm the exact success marker `MFX_A04_P55_NATIVE_H4_D1_DRIVE_PAIR_SHA_READBACK_PASS`, two provider series and zero broker orders.
4. Independently read the new H4 and D1 Chunk+Manifest JSON from private Google Drive, verify canonical SHA and exact symbol/time-axis/provenance, then mark native H4/D1 real Cache ACCEPTED. Until then remain STAGED.
