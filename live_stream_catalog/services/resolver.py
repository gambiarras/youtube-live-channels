import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from streamlink import Streamlink

from live_stream_catalog.models import Channel
from live_stream_catalog.plugins import register_custom_plugins
from live_stream_catalog.services.expiry import extract_expiry_from_stream_url, utc_now

logger = logging.getLogger(__name__)


def build_streamlink_session() -> Streamlink:
    session = Streamlink()
    register_custom_plugins(session)
    return session


def resolve_channel(channel: Channel) -> Channel:
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
    results: list[Channel] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(resolve_channel, channel): channel for channel in channels}

        for future in as_completed(futures):
            results.append(future.result())

    return results