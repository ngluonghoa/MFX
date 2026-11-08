# M2/P0.9 — Drive v3 raw-blob wire contract, SYNTHETIC ONLY

**Purpose:** progress from the M2/P0.8 pure memory cache toward a verifiable Drive file adapter, while respecting the user's selected Google Drive destination and the mandatory 5→20→1→20 scope-reuse acceptance case.

## Code boundary

`src/forex_trading/google_drive_wire_contract.py` builds real-shaped Google Drive REST v3 `files.list`, `files.create?uploadType=multipart`, `files.get` metadata and `files.get?alt=media` requests for an **injected callable transport**. A concrete OAuth-backed transport **does not exist** in this repo. The current test double intercepts every request in memory, and therefore **zero live Google Drive network requests or persistent raw blobs** have been demonstrated.

The port admits ONLY bounded bytes beginning with `FX_SYNTHETIC_CACHE_V1\n`. That prefix is an *engineering fixture convention*, NOT a security classifier or a license gate: it must NEVER be used to upload live Forex data or to infer legal permission. No token, account ID, secret, production price candle, or licensed raw feed is committed.

## Security/integrity design

1. Each immutable fixture blob is named using opaque partition SHA256 + full content SHA256. Repeating the exact payload must first query for the same filename. Drive filenames are not unique, so duplicates/paginated/partial responses fail closed; no unsafely selected first match.
2. When missing, build a Drive v3 multipart upload request containing metadata (`name`, `mimeType=application/octet-stream`, `parents=[approved staging folder]`) and binary payload. A fake server checks exact request shape.
3. Validate returned and independently fetched metadata: expected ID, name, MIME, precise folder parent, byte length and Drive `md5Checksum`.
4. Independently download the media and compare actual bytes with expected **SHA256**, MD5 and size. MD5 is only for matching the Google Drive binary-file metadata; SHA256 guards application-level contents.
5. On upload 429/5xx or an ambiguous failure, **never blindly retry POST**. An earlier write could have committed: first reconcile by exact filename/digest and avoid duplicate creation. In this contract failures are surfaced and require a caller-driven new attempt rather than auto retry.
6. Metadata/completeness corruption, orphaned references, duplicated filenames, 404s, wrong parent or body, and readback mismatch must fail closed.
7. No content overwrite, delete, active pointer publication, distributed writer lease, externally witnessed anti-rollback anchor or encryption is claimed by this module.

## Why this is not an operational Google Drive Cache

- The existing connected Drive plugin supports actual folder creation and docs, but no raw OAuth/HTTP transport has been instantiated by this code. Test HTTP verbs and URLs are intercepted by an in-memory FakeDriveWire.
- Google Drive API does not make a list-check + create sequence a globally atomic create-if-absent: a real deployment needs independently enforced single-writer/lease/serialization, and after-commit readback/concurrency audit.
- Google Drive binary file revisions are not an adequate independent long-term rollback witness; old revisions can be garbage-collected. Use explicit immutable versioned objects, retention and separately verified anchors. Reference: https://developers.google.com/workspace/drive/api/guides/manage-revisions
- No client-side encryption/key management or region/ACL review exists. No vendor account-specific evidence grants raw BID/ASK caching, derived storage, retention, backtest or replay. Nothing in this work authorizes real market-data uploads.
- Drive is the **chosen storage destination**, not a compute host or five-minute scheduler. Actual Drive API requests/bytes, provider historical range requests/bytes, and measured latency = NOT RUN/NOT MEASURED.

## Tests and next milestones

`tests/test_google_drive_wire_contract.py` covers synthetic multipart request shape, metadata/body/SHA256 verification, content-addressed deduplication, a wire-level **5→20→1→20** fixture reuse sequence, same-partition changed-content new immutable generation, duplicate filename, pagination, malformed JSON, wrong checksum, corrupted content, 429/503, missing media, oversize, unmarked input, invalid folder/partition, and wrong transport response type. These tests do not demonstrate cloud persistence.

**NEXT:** after the provider/account rights and Drive encryption/ACL/key/residency approval gates, implement a separately reviewed authenticated real blob transport, measured cloud quota/latency and lease + immutable manifest pointer transaction with verified recovery across sessions. Real provider delta must be separately qualified; do not reinterpret fake transport counters as real speed. Preserve DEC-FX-020/021/022 and current synthetic 5→20→1→20 acceptance.
