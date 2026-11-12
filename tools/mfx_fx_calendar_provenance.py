"""A04/P0.93 — source-scoped FX session evidence, offline/no automatic waiver.

Public publisher pages are references, NOT externally authenticated calendar
snapshots. Broker execution hours, venue hours and Twelve Data Forex API v2
data-feed *availability* have different meanings. A documented 24/7 feed
operation is NOT an SLA for every 5-minute candle and does not prove that
the actual MFX /time_series subscription resolves to the v2 product.

This pure classifier makes zero network/Drive/provider/broker calls, cannot
verify publication timestamps or entitlements, and NEVER approves an H4
calendar gap waiver, live source switch, numeric signal or broker order.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

SCHEMA = "MFX_A04_P93_FX_CALENDAR_PROVENANCE_NO_WAIVER_V1"
WRITER_BLOB_SHA = "5162b6068a5ba6bfa51d4fb1b57e81fd40a3a99e"
WRITER_PATH = "tools/run_a04_p45_cloud_twelve_data_cache.py"
WRITER_ENDPOINT = "https://api.twelvedata.com/time_series"
WRITER_SYMBOL = "EUR/USD"
WRITER_INTERVAL = "5min"
WRITER_TIMEZONE = "UTC"
H4 = timedelta(hours=4)
MAX_H4_SLOTS = 72

# Static excerpts are paraphrased publication facts, not scraped data.
# Scope is intentionally more precise than a generic 'FX market calendar'.
@dataclass(frozen=True, slots=True)
class OfficialPublicReference:
    source_id: str
    publisher: str
    url: str
    scope: str
    published_on: str | None
    assertion: str


OFFICIAL_REFERENCES = {
    "TWELVE_DATA_FOREX_V2": OfficialPublicReference(
        "TWELVE_DATA_FOREX_V2", "Twelve Data",
        "https://support.twelvedata.com/en/articles/12520817-forex-api-v2",
        "FEED_SERVICE_AVAILABILITY", "2025-12-03",
        "Forex API v2 service describes 24/7 operation incl. weekends; "
        "does not explicitly promise each M5 bar or prove MFX plan version.",
    ),
    "TWELVE_DATA_FOREX_TZ": OfficialPublicReference(
        "TWELVE_DATA_FOREX_TZ", "Twelve Data",
        "https://support.twelvedata.com/en/articles/5745849-timezones",
        "DATA_TIMESTAMP_DEFAULT", "2025-05-13",
        "Forex default timezone is Australia/Sydney; the MFX writer "
        "explicitly requests UTC intraday output.",
    ),
    "OANDA_US_FX_HOURS": OfficialPublicReference(
        "OANDA_US_FX_HOURS", "OANDA",
        "https://www.oanda.com/us-en/trading/hours-of-operation/",
        "BROKER_EXECUTION_SESSION", None,
        "This OANDA division lists Sunday 17:05 to Friday 16:59 "
        "New York time, with a daily six-minute break; not a Twelve Data SLA.",
    ),
    "CME_FX_SPOT_PLUS_2026": OfficialPublicReference(
        "CME_FX_SPOT_PLUS_2026", "CME Group",
        "https://www.cmegroup.com/trading-hours.html",
        "VENUE_FX_SPOT_PLUS_SESSION", None,
        "CME's 2026 FX Spot+ hours are venue-specific with a daily "
        "break; this is not a rule for Twelve Data EUR/USD composite candles.",
    ),
}


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _gap(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("P093_GAP_TYPED_UTC_LABEL_REQUIRED")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("P093_GAP_UTC_LABEL_INVALID") from exc
    if (not _utc(stamp) or stamp.hour % 4 or stamp.minute or stamp.second
            or stamp.microsecond or stamp.isoformat() != value):
        raise ValueError("P093_GAP_EXACT_4H_UTC_REQUIRED")
    return stamp


@dataclass(frozen=True, slots=True)
class FXCalendarEvidenceReview:
    schema: str
    status: str
    source_ids: tuple[str, ...]
    published_reference_urls: tuple[str, ...]
    source_scopes: tuple[str, ...]
    writer_git_blob_sha: str
    mfx_writer_endpoint: str
    mfx_writer_symbol: str
    mfx_writer_interval: str
    mfx_writer_timezone: str
    declared_gap_h4_slots: int
    utc_weekend_gap_candidates: int
    utc_weekday_gap_candidates: int
    first_party_twelve_data_v2_reference_present: bool
    other_broker_or_venue_session_reference_present: bool
    scope_mismatch_requires_separate_review: bool
    source_document_observation_not_authenticated: bool = True
    actual_mfx_feed_v2_subscription_verified: bool = False
    exact_provider_m5_weekend_bar_sla_verified: bool = False
    official_calendar_exception_for_each_gap_verified: bool = False
    publisher_source_html_digest_verified: bool = False
    independently_authenticated_publication_asof: bool = False
    market_session_or_DST_exception_granted: bool = False
    automatic_weekend_gap_waiver_allowed: bool = False
    source_h4_cutover_authorized: bool = False
    may_reduce_native_h4_requests: bool = False
    may_change_sydney_native_d1: bool = False
    licensed_bid_ask_or_numeric_fx_signals_authorized: bool = False
    broker_orders_authorized: bool = False
    provider_calls_by_this_module: int = 0
    drive_writes_by_this_module: int = 0
    broker_orders_by_this_module: int = 0


def review_fx_calendar_provenance(
    source_ids: tuple[str, ...],
    observed_missing_h4_utc: tuple[str, ...], *,
    reviewed_asof_utc: datetime,
    source_writer_blob_sha: str = WRITER_BLOB_SHA,
) -> FXCalendarEvidenceReview:
    """Cross-scope, bounded policy review using caller-supplied references.

    No network access and no signature/hash of publisher HTML is included.
    Documentation itself cannot certify which exact feed MFX received.
    """
    if (type(source_ids) is not tuple or not 1 <= len(source_ids) <= 4
            or any(type(s) is not str or s not in OFFICIAL_REFERENCES
                   for s in source_ids) or len(source_ids) != len(set(source_ids))):
        raise ValueError("P093_OFFICIAL_SOURCE_IDS_REQUIRED_UNIQUE")
    if (not _utc(reviewed_asof_utc)
            or type(source_writer_blob_sha) is not str
            or source_writer_blob_sha != WRITER_BLOB_SHA):
        raise ValueError("P093_UTC_OR_WRITER_SOURCE_BLOB_MISMATCH")
    if (type(observed_missing_h4_utc) is not tuple
            or len(observed_missing_h4_utc) > MAX_H4_SLOTS):
        raise ValueError("P093_BOUNDED_TYPED_GAP_TUPLE_REQUIRED")
    labels = tuple(_gap(s) for s in observed_missing_h4_utc)
    if (any(a >= b for a, b in zip(labels, labels[1:]))
            or any(t + H4 > reviewed_asof_utc for t in labels)
            or (labels and labels[-1] - labels[0]
                > (MAX_H4_SLOTS-1)*H4)):
        raise ValueError("P093_GAP_CLOCK_ORDER_OR_FUTURE_INVALID")
    # A written article's publication date is merely a source claim until
    # externally preserved/signed. Still reject impossible past-asof joins.
    for sid in source_ids:
        published = OFFICIAL_REFERENCES[sid].published_on
        if published is not None and reviewed_asof_utc.date() < (
                datetime.strptime(published, "%Y-%m-%d").date()):
            raise ValueError("P093_DOCUMENT_POSTDATES_REVIEW_ASOF")
    td = "TWELVE_DATA_FOREX_V2" in source_ids
    comparator = any(
        OFFICIAL_REFERENCES[s].scope in (
            "BROKER_EXECUTION_SESSION", "VENUE_FX_SPOT_PLUS_SESSION")
        for s in source_ids
    )
    if not labels:
        status = "P093_REFERENCES_ONLY_NO_MISSING_H4_SLOT_OBSERVED"
    elif not td:
        status = "P093_NO_MATCHED_FEED_VERSION_CANNOT_WAIVE_GAP"
    elif comparator:
        status = "P093_DELIVERY_VS_EXECUTION_SCOPE_DIVERGENCE_NO_WAIVER"
    else:
        status = "P093_24_7_FEED_SERVICE_NOT_M5_CANDLE_SLA_NO_WAIVER"
    return FXCalendarEvidenceReview(
        schema=SCHEMA, status=status, source_ids=source_ids,
        published_reference_urls=tuple(
            OFFICIAL_REFERENCES[s].url for s in source_ids),
        source_scopes=tuple(OFFICIAL_REFERENCES[s].scope for s in source_ids),
        writer_git_blob_sha=source_writer_blob_sha,
        mfx_writer_endpoint=WRITER_ENDPOINT,
        mfx_writer_symbol=WRITER_SYMBOL,
        mfx_writer_interval=WRITER_INTERVAL,
        mfx_writer_timezone=WRITER_TIMEZONE,
        declared_gap_h4_slots=len(labels),
        utc_weekend_gap_candidates=sum(t.weekday() >= 5 for t in labels),
        utc_weekday_gap_candidates=sum(t.weekday() < 5 for t in labels),
        first_party_twelve_data_v2_reference_present=td,
        other_broker_or_venue_session_reference_present=comparator,
        scope_mismatch_requires_separate_review=td and comparator,
    )
