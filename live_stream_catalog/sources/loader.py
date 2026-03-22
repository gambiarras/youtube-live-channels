import json
import logging
from importlib import resources

from live_stream_catalog.models import Channel
from live_stream_catalog.sources.registry import get_resource_registry

logger = logging.getLogger(__name__)


def _load_single_resource(resource_name: str, source_type: str, default_resolution: str) -> list[Channel]:
    with resources.files("live_stream_catalog.resources").joinpath(resource_name).open("r", encoding="utf-8") as file:
        raw = json.load(file)

    channels: list[Channel] = []
    for item in raw:
        item = dict(item)
        item["source_type"] = source_type
        channels.append(Channel.from_dict(item, default_resolution=default_resolution))

    return channels


def _deduplicate(channels: list[Channel]) -> list[Channel]:
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    result: list[Channel] = []

    for channel in channels:
        if channel.id in seen_ids:
            logger.warning("Duplicate channel id skipped: %s", channel.id)
            continue

        if channel.source_url in seen_urls:
            logger.warning("Duplicate source URL skipped: %s", channel.source_url)
            continue

        seen_ids.add(channel.id)
        seen_urls.add(channel.source_url)
        result.append(channel)

    return result


def load_catalog(default_resolution: str = "best") -> list[Channel]:
    channels: list[Channel] = []

    for resource_name, source_type in get_resource_registry():
        channels.extend(_load_single_resource(resource_name, source_type, default_resolution))

    return _deduplicate(channels)