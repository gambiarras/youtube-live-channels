import logging

from live_stream_catalog.config import AppConfig
from live_stream_catalog.io import write_json_atomic
from live_stream_catalog.services.metadata import build_run_metadata
from live_stream_catalog.services.resolver import resolve_channels
from live_stream_catalog.sources import load_catalog

logger = logging.getLogger(__name__)

SOURCE_PRIORITY = {
    "youtube": 30,
    "twitch": 20,
    "kick": 25,
    "unknown": 10,
}


def _sort_for_resolution(channels):
    return sorted(channels, key=lambda item: SOURCE_PRIORITY.get(item.source_type, 10))


def run_build(config: AppConfig) -> None:
    logger.info("Starting full build")

    catalog = load_catalog(default_resolution=config.default_resolution)
    catalog = _sort_for_resolution(catalog)
    resolved = resolve_channels(catalog, max_workers=config.max_workers)

    resolved.sort(key=lambda item: item.id.casefold())

    write_json_atomic(config.output_path, [channel.to_dict() for channel in resolved])

    metadata = build_run_metadata(resolved)
    write_json_atomic(config.meta_output_path, metadata.to_dict())

    logger.info(
        "Build finished total=%s resolved=%s offline=%s errors=%s",
        metadata.total_channels,
        metadata.resolved_channels,
        metadata.offline_channels,
        metadata.error_channels,
    )