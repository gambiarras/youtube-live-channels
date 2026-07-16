import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from streamlink import Streamlink

from live_stream_catalog.models import Channel
from live_stream_catalog.plugins import register_custom_plugins
from live_stream_catalog.services.expiry import (
    extract_expiry_from_stream_url,
    parse_iso_datetime,
    utc_now,
)

logger = logging.getLogger(__name__)

DIRECT_STREAM_SOURCE_TYPES = {"script_discovered"}
SERIAL_RESOLVE_SOURCE_TYPES = {"youtube"}
TRANSIENT_RESOLVE_ERROR_MARKERS = (
    "429",
    "too many requests",
    "google.com/sorry",
    "rate limit",
    "rate-limit",
    "ratelimit",
    "temporarily blocked",
)


def _is_pre_resolved(channel: Channel) -> bool:
    if channel.status != "resolved" or not channel.stream_url:
        return False

    return channel.source_type in DIRECT_STREAM_SOURCE_TYPES or channel.source_url == channel.stream_url


def _is_transient_resolve_error(exc: Exception) -> bool:
    message = str(exc).casefold()
    return any(marker in message for marker in TRANSIENT_RESOLVE_ERROR_MARKERS)


def _existing_stream_url_has_expired(channel: Channel) -> bool:
    expires_at = parse_iso_datetime(channel.expires_at)
    if expires_at is None:
        extracted_expires_at, _ttl_seconds = extract_expiry_from_stream_url(channel.stream_url)
        expires_at = parse_iso_datetime(extracted_expires_at)

    return expires_at is not None and expires_at <= utc_now()


def _preserve_existing_stream_url(channel: Channel, exc: Exception) -> Channel:
    channel.status = "resolved"
    channel.error = f"transient_resolve_error: {exc}"
    channel.resolved_at = utc_now().isoformat()
    channel.expires_at, channel.ttl_seconds = extract_expiry_from_stream_url(channel.stream_url)
    return channel


def build_streamlink_session() -> Streamlink:
    session = Streamlink()
    register_custom_plugins(session)
    return session


def resolve_channel(channel: Channel) -> Channel:
    if _is_pre_resolved(channel):
        channel.error = None
        channel.resolved_at = utc_now().isoformat()
        channel.expires_at, channel.ttl_seconds = extract_expiry_from_stream_url(channel.stream_url)
        return channel

    session = build_streamlink_session()

    try:
        streams = session.streams(channel.source_url)
        stream = streams.get(channel.resolution) or streams.get("best")

        if stream is None:
            channel.status = "offline"
            channel.error = "no_stream_found"
            channel.stream_url = None
            channel.resolved_at = utc_now().isoformat()
            channel.expires_at = None
            channel.ttl_seconds = None
            return channel

        channel.stream_url = stream.url
        channel.status = "resolved"
        channel.error = None
        channel.resolved_at = utc_now().isoformat()
        channel.expires_at, channel.ttl_seconds = extract_expiry_from_stream_url(stream.url)
        return channel

    except Exception as exc:
        if channel.stream_url and _is_transient_resolve_error(exc):
            if not _existing_stream_url_has_expired(channel):
                logger.warning(
                    "Keeping previous stream URL after transient resolve error id=%s source_url=%s error=%s",
                    channel.id,
                    channel.source_url,
                    exc,
                )
                return _preserve_existing_stream_url(channel, exc)

            logger.warning(
                "Dropping expired stream URL after transient resolve error id=%s source_url=%s error=%s",
                channel.id,
                channel.source_url,
                exc,
            )

        logger.exception("Failed to resolve channel id=%s source_url=%s", channel.id, channel.source_url)
        channel.status = "error"
        channel.error = str(exc)
        channel.stream_url = None
        channel.resolved_at = utc_now().isoformat()
        channel.expires_at = None
        channel.ttl_seconds = None
        return channel

    finally:
        try:
            session.close()
        except Exception:
            pass


def resolve_channels(channels: list[Channel], max_workers: int) -> list[Channel]:
    pre_resolved = [channel for channel in channels if _is_pre_resolved(channel)]
    unresolved = [channel for channel in channels if not _is_pre_resolved(channel)]
    serial_unresolved = [
        channel for channel in unresolved if channel.source_type in SERIAL_RESOLVE_SOURCE_TYPES
    ]
    parallel_unresolved = [
        channel for channel in unresolved if channel.source_type not in SERIAL_RESOLVE_SOURCE_TYPES
    ]
    results = [resolve_channel(channel) for channel in pre_resolved]

    if parallel_unresolved:
        worker_count = max(1, min(max_workers, len(parallel_unresolved)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(resolve_channel, channel): channel for channel in parallel_unresolved}

            for future in as_completed(futures):
                results.append(future.result())

    results.extend(resolve_channel(channel) for channel in serial_unresolved)

    return results
