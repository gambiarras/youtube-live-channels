import logging

from live_stream_catalog.config import AppConfig
from live_stream_catalog.io import load_channels_file, write_json_atomic
from live_stream_catalog.services.expiry import needs_refresh
from live_stream_catalog.services.metadata import build_run_metadata
from live_stream_catalog.services.resolver import resolve_channels
from live_stream_catalog.sources.script_discovered_catalog import (
    SCRIPT_DISCOVERED_SOURCE_TYPE,
    load_configured_rest_catalogs,
)

logger = logging.getLogger(__name__)

MAX_AGE_BY_SOURCE = {
    "youtube": 1800,
    "kick": 1800,
    "twitch": 1800,
}

DYNAMIC_SOURCE_TYPES = {SCRIPT_DISCOVERED_SOURCE_TYPE}


def run_refresh(config: AppConfig) -> None:
    logger.info("Starting partial refresh")

    current_channels = load_channels_file(
        config.output_path,
        default_resolution=config.default_resolution,
    )

    if not current_channels:
        logger.info("No existing catalog found, falling back to full build")
        from live_stream_catalog.services.build import run_build
        run_build(config)
        return

    dynamic_channels = [
        channel
        for channel in current_channels
        if channel.source_type in DYNAMIC_SOURCE_TYPES
    ]
    static_channels = [
        channel
        for channel in current_channels
        if channel.source_type not in DYNAMIC_SOURCE_TYPES
    ]

    try:
        dynamic_channels = load_configured_rest_catalogs(
            default_resolution=config.default_resolution,
            continue_on_error=False,
        )
    except Exception as exc:
        logger.exception("Failed to refresh dynamic catalogs, keeping existing channels error=%s", exc)

    to_refresh = [
        channel
        for channel in static_channels
        if needs_refresh(
            channel,
            config.min_ttl_seconds,
            max_age_by_source=MAX_AGE_BY_SOURCE,
        )
    ]
    to_keep = [
        channel
        for channel in static_channels
        if not needs_refresh(
            channel,
            config.min_ttl_seconds,
            max_age_by_source=MAX_AGE_BY_SOURCE,
        )
    ]

    logger.info(
        "Refresh selection total=%s refresh=%s keep=%s",
        len(current_channels),
        len(to_refresh),
        len(to_keep) + len(dynamic_channels),
    )

    refreshed = resolve_channels(to_refresh, max_workers=config.max_workers)

    merged = to_keep + refreshed + dynamic_channels
    merged.sort(key=lambda item: item.id.casefold())

    write_json_atomic(config.output_path, [channel.to_dict() for channel in merged])

    metadata = build_run_metadata(merged)
    write_json_atomic(config.meta_output_path, metadata.to_dict())

    logger.info(
        "Refresh finished total=%s resolved=%s offline=%s errors=%s",
        metadata.total_channels,
        metadata.resolved_channels,
        metadata.offline_channels,
        metadata.error_channels,
    )
