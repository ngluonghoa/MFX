# M2/P0.10 — Actual Google Drive connector smoke: synthetic chunk + immutable manifest

**Date:** 2026-11-07 (Asia/Ho_Chi_Minh); independent test using the *already connected* Google Drive connector. This is **real Google Drive file upload/download of harmless synthetic text**, not the Python `SyntheticGoogleDriveBlobPort` from M2/P0.9. This milestone deliberately does **not** enable Forex price cache, broker data, automated trading, live 5-minute scanning or distributed atomic commit.

## Real connector actions, measured bytes and verification

Destination: Forex Trading 1.0 private project [cache staging root](https://drive.google.com/drive/folders/12iWh528iFnfF6zyHBGpI4WFOSrrubmX5).

| Artifact | Real Google Drive location | Exported/uploaded bytes | Verified SHA-256 |
| --- | --- | ---: | --- |
| [SYNTHETIC chunk](https://drive.google.com/file/d/1HgjhwKJW2JzuO_OL8ODl45GdsW9bGv3h/view) | `01_IMMUTABLE_CHUNKS__STAGING` folder ID `1mE7Zx29kDjyN8DYfvZn4HYx-OIoYaScw` | 141 | `3399fba3e2dee9557bdff2f2b00f393dffd584083c2632378ee5f5864716c81d` |
| [SYNTHETIC manifest](https://drive.google.com/file/d/1j7yevV6EgH7fyKj5uok5iOqrF1dGBegK/view) | `00_MANIFESTS_AND_INDEX__STAGING` folder ID `1OPBHzq5sPNV9ohqlsfi_I5e35ve1qvkD` | 439 | `fccca2450f150bc1839ef6e266190200526e74a6d22c6365ab48d7533a9e7b9a` |

- Created two temporary **Google Docs** containing explicitly identified fake TESTPAIR00 metadata, exported both via Google Drive `files.export` as `text/plain`, received connector-local file references, and uploaded two **ordinary raw text files** via `Google_Drive.upload_file(file_uri, parent_folder_id, file_name)`.
- Google Docs text export added a UTF-8 BOM and converted newlines to CRLF; exported **byte representation** was what was measured. Do not use Docs export to generate production candle bytes.
- Downloaded each raw file separately through `Google_Drive.fetch(download_raw_file=true, include_base64=false)` and checked byte-for-byte equality with original exported bytes inside the current execution container. SHA256 for each matched; chunk MD5 `eeef04bb1095d763864a70474f21866e`, and JSON manifest independently references the *correct* chunk Google file ID, 141-byte size, SHA256 and MD5. Re-read chunk after removing the temporary source Doc and verified it still existed independently (141-byte provider metadata and file listing).
- The two temporary source Docs were **deleted**. The two immutable smoke artifacts are intentionally retained in dedicated staging folders, not in Google Docs sources or the Forex licensed data partitions. Original Google Drive metadata for chunk showed 141 bytes, parent folder ID and owner-only permission at the time of read. No credentials/user account numbers/broker data or real FX quotes uploaded.

## Exact scope and security caveats

- **Real read/write capability observed:** yes, for two connector-managed raw `text/plain` files. This shows that the connected Google Drive user can store and retrieve ordinary files in the Forex staging folders, not that a Python scanner's OAuth transport or a live Google Drive API adapter exists.
- **Integrity observed:** source-export vs downloaded bytes matched; content SHA256/MD5 and manifest pointer were consistent at the time of this test. An application-level hash is not a vendor-signed receipt, authentic revision watermark, trusted external anti-rollback witness, encryption proof or guarantee of future availability.
- **No performance claim:** a pair of tiny smoke files is not a statistically useful latency/throughput benchmark for 20 pairs/200 partitions every 5 minutes; no per-operation wall timings, quota pressure or source HTTP request counts measured. The synthetic 5→20→1→20 cache core was tested separately in PRs #23/#25.
- **No atomic multi-file commit:** Google Drive upload of immutable chunk then manifest is not an all-or-nothing transaction; a crash in between can leave an orphan. No conditional CAS/lease/fencing, stale-writer conflict control, independent rollback witness or automatic recovery was implemented here.
- **No encryption/key approval:** Drive default account storage is not equivalent to independently approved client-side encryption with customer-held keys, explicit residency/ACL review or scoped retention/revocation tests.
- **No data entitlement:** the selected real vendor account/plan/region has not been independently qualified for storing historical native BID/ASK, derived indicators, replay/backtest, retention and source revisions. The marker `FX_SYNTHETIC_CACHE_V1` is a test convention only, not a security classifier.
- **No live market scan:** actual provider FX API requests = 0; trades = 0; real market-data cache writes = 0.

## Code and follow-on acceptance

`src/forex_trading/synthetic_drive_receipt_validation.py` provides a **pure offline** strict validator that accepts downloaded fixture bytes and copied Drive connector metadata, rejects changes to content-address filenames, parent folders, MIME, broken manifest references, SHA/MD5/size differences, duplicate JSON keys, unapproved extra fields, or attempts to label the fixture as licensed real FX. It always returns `may_cache_real_fx=False`, `may_trade=False`, `may_claim_atomic_commit=False` and `may_claim_external_rollback_witness=False`. This validator does not call Drive and does not independently attest that metadata is authentic.

Unit tests reconstruct the *exact observed* byte representations, including BOM/CRLF, and confirm fixture digests. **Do not interpret CI-only tests as additional real Drive uploads.**

**Next:** implement a properly authenticated, scoped raw-file adapter with approved key management & rights; prove readback under restart/another session, reject duplicate names with a real coordination strategy, add manifest generation/lease/fencing and recovery, then benchmark actual Drive I/O 5→20→1→20 and provider deltas, followed by full L2–L5. Until verified, this stage is **CONNECTOR_SMOKE_ONLY**, not operational persistent Forex cache.
