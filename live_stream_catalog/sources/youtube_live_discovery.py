import json
import logging
from dataclasses import dataclass
from importlib import resources
from urllib.parse import urlparse

from live_stream_catalog.models import Channel


logger = logging.getLogger(__name__)


CONFIG_RESOURCE_NAME = "youtube_live_discovery_channels.json"
SOURCE_TYPE = "youtube"
YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"


@dataclass(slots=True, frozen=True)
class YouTubeLiveDiscoveryConfig:
    id: str
    name: str
    logo: str
    group: str
    handle: str | None = None
    streams_url: str | None = None
    url: str | None = None
    fallback_url: str | None = None
    use_fallback_when_empty: bool = True
    max_results: int = 50
    include_upcoming: bool = False
    resolution: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "YouTubeLiveDiscoveryConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            logo=data.get("logo", ""),
            group=data.get("group", "general"),
            handle=data.get("handle"),
            streams_url=data.get("streams_url"),
            url=data.get("url"),
            fallback_url=data.get("fallback_url"),
            use_fallback_when_empty=bool(data.get("use_fallback_when_empty", True)),
            max_results=int(data.get("max_results", 50)),
            include_upcoming=bool(data.get("include_upcoming", False)),
            resolution=data.get("resolution"),
        )


def load_config_resource() -> list[YouTubeLiveDiscoveryConfig]:
    resource = resources.files("live_stream_catalog.resources").joinpath(CONFIG_RESOURCE_NAME)
    if not resource.is_file():
        return []

    return [
        YouTubeLiveDiscoveryConfig.from_dict(item)
        for item in json.loads(resource.read_text(encoding="utf-8"))
    ]


def _streams_url(config: YouTubeLiveDiscoveryConfig) -> str:
    if config.streams_url:
        return config.streams_url.rstrip("/")

    if config.url:
        url = config.url.rstrip("/")
        if url.endswith("/streams"):
            return url
        if url.endswith("/live"):
            return f"{url[:-5]}/streams"
        return f"{url}/streams"

    if not config.handle:
        raise ValueError(f"YouTube live discovery config requires handle or url: {config.id}")

    handle = config.handle if config.handle.startswith("@") else f"@{config.handle}"
    return f"https://www.youtube.com/{handle}/streams"


def _fallback_url(config: YouTubeLiveDiscoveryConfig) -> str:
    if config.fallback_url:
        return config.fallback_url

    if config.streams_url:
        url = config.streams_url.rstrip("/")
        if url.endswith("/streams"):
            return f"{url[:-8]}/live"
        return f"{url}/live"

    if config.url:
        url = config.url.rstrip("/")
        if url.endswith("/streams"):
            return f"{url[:-8]}/live"
        return config.url

    handle = config.handle if config.handle and config.handle.startswith("@") else f"@{config.handle}"
    return f"https://www.youtube.com/{handle}/live"


def _entry_video_id(entry: dict) -> str | None:
    video_id = entry.get("id")
    if video_id:
        return str(video_id)

    url = entry.get("url")
    if not url:
        return None

    parsed = urlparse(str(url))
    if parsed.netloc.endswith("youtube.com") and parsed.path == "/watch":
        from urllib.parse import parse_qs

        return parse_qs(parsed.query).get("v", [None])[0]

    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/") or None

    return None


def _entry_is_usable(entry: dict, include_upcoming: bool) -> bool:
    live_status = entry.get("live_status")
    if live_status == "is_live":
        return True

    if include_upcoming and live_status == "is_upcoming":
        return True

    return entry.get("is_live") is True


def _entry_title(config: YouTubeLiveDiscoveryConfig, entry: dict) -> str:
    title = entry.get("title")
    if title:
        return f"{config.name} - {title}"
    return config.name


def _entry_logo(config: YouTubeLiveDiscoveryConfig, entry: dict) -> str:
    thumbnails = entry.get("thumbnails")
    if isinstance(thumbnails, list) and thumbnails:
        thumbnail = thumbnails[-1]
        if isinstance(thumbnail, dict) and thumbnail.get("url"):
            return str(thumbnail["url"])

    return config.logo


def _youtube_dl_options(max_results: int) -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": max_results,
    }


def _fallback_channel(config: YouTubeLiveDiscoveryConfig) -> Channel:
    return Channel(
        id=config.id,
        name=config.name,
        source_url=_fallback_url(config),
        logo=config.logo,
        group=config.group,
        source_type=SOURCE_TYPE,
        resolution=config.resolution or "best",
    )


def discover_live_channels(
    config: YouTubeLiveDiscoveryConfig,
    youtube_dl_cls=None,
) -> list[Channel]:
    if youtube_dl_cls is None:
        from yt_dlp import YoutubeDL

        youtube_dl_cls = YoutubeDL

    streams_url = _streams_url(config)
    with youtube_dl_cls(_youtube_dl_options(config.max_results)) as ydl:
        payload = ydl.extract_info(streams_url, download=False)

    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not entries:
        return [_fallback_channel(config)] if config.use_fallback_when_empty else []

    channels: list[Channel] = []
    seen_video_ids: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict) or not _entry_is_usable(entry, config.include_upcoming):
            continue

        video_id = _entry_video_id(entry)
        if not video_id or video_id in seen_video_ids:
            continue

        seen_video_ids.add(video_id)
        source_url = YOUTUBE_WATCH_URL.format(video_id=video_id)
        channels.append(
            Channel(
                id=f"{config.id}.{video_id}",
                name=_entry_title(config, entry),
                source_url=source_url,
                logo=_entry_logo(config, entry),
                group=config.group,
                source_type=SOURCE_TYPE,
                resolution=config.resolution or "best",
            )
        )

    if not channels and config.use_fallback_when_empty:
        return [_fallback_channel(config)]

    return channels


def load_youtube_live_discovery_channels(
    default_resolution: str = "best",
    youtube_dl_cls=None,
    configs: list[YouTubeLiveDiscoveryConfig] | None = None,
) -> list[Channel]:
    channels: list[Channel] = []

    for config in configs if configs is not None else load_config_resource():
        config = YouTubeLiveDiscoveryConfig(
            id=config.id,
            name=config.name,
            logo=config.logo,
            group=config.group,
            handle=config.handle,
            streams_url=config.streams_url,
            url=config.url,
            fallback_url=config.fallback_url,
            use_fallback_when_empty=config.use_fallback_when_empty,
            max_results=config.max_results,
            include_upcoming=config.include_upcoming,
            resolution=config.resolution or default_resolution,
        )

        try:
            channels.extend(discover_live_channels(config, youtube_dl_cls=youtube_dl_cls))
        except Exception as exc:
            logger.exception(
                "Failed to discover YouTube live streams id=%s url=%s error=%s",
                config.id,
                _streams_url(config),
                exc,
            )

    return channels
