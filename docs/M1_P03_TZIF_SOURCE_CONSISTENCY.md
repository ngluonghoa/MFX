# M1/P0.3 — TZif byte pin and causal BID/ASK source coherence

**Scope: read-only synthetic software invariants.** The existing SourceCalendarPolicy uses installed ZoneInfo and a tzdb revision *claim* only. This PR adds an independent way to evaluate **known TZif bytes** with a caller-provided expected SHA-256, without falling back to a host's installed TZPATH. Neither the expected SHA nor an IANA zone name is a third-party authenticity attestation unless the vendor's signed/published source and legal rights are independently verified.

## 1. TZif provenance
- TzifArtifact: provider/source revision, claimed zone and tzdb revision, first-known UTC, exact raw TZif bytes, expected digest. Validate structure and hash at construction; malformed/tampered bytes fail closed.
- resolve_wall_with_pinned_tzif: decode TZif payload with ZoneInfo.from_file; refuse future-known payload, implicit fold during autumn overlap, spring nonexistent time, invalid input.
- assess_tzif_policy: check pinned artifact against vendor-declared calendar policy for provider/zone/version and as-of. It always returns source_independently_attested=False and permission_to_trade=False.
- Unit fixture is tiny, original **synthetic TZif v1**, with exactly two 2026 transitions and SHA-256 frozen in the tests. This is not an official IANA distribution, cannot validate real venue rules, and does not pin production tzdb. The existing OS-based SourceCalendarPolicy remains for design-level tests; production selection of a trusted, versioned real tzdb is still blocked.

## 2. BID/ASK source coherence
- BidAskSourceManifest binds a claimed dataset digest, instrument, time interval, source calendar/aggregation, provider, separate BID/ASK stream IDs and revision IDs, source timezone policy and first-known UTC.
- assess_bid_ask_side_pair rejects missing MID-only sides, future-known source manifests/quote revisions, conflicting provider, interval, side, clock/aggregation versions, incomplete/open/unverified bars. It calls the independent M1/P0.1 read-only bar gates and always reports trade_permission=False.
- It **does not** compare BID/ASK OHLC by numeric shape as if asynchronous vendor streams shared identical tick timestamps. It does not independently verify rights, declared digest, feed latency, or a broker-executable fill.

## 3. Acceptance boundaries
Synthetic tests are not equivalent to FX-DC-01..08 full provider verification or FX-VR rollback proof. No engine rules for B2/S2, no live broker actions or real historical market data. The 18 approved design zone labels remain unchanged; FX-B9 research only. GitHub private PR/CI, no Mac work.
