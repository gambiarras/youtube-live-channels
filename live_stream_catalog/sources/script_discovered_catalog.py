import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from importlib import resources
from urllib.parse import urlencode, urljoin

import requests

from live_stream_catalog.models import Channel


logger = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


SUPABASE_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9.-]+\.supabase\.co")
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
SCRIPT_DISCOVERED_SOURCE_TYPE = "script_discovered"
CONFIG_RESOURCE_NAME = "script_discovered_catalogs.json"


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "script":
            return

        attrs_dict = dict(attrs)
        src = attrs_dict.get("src")
        if src:
            self.scripts.append(src)


@dataclass(slots=True, frozen=True)
class DiscoveredRestCatalog:
    site_url: str
    script_url: str
    api_base_url: str
    anon_key: str

    def endpoint(self, table_name: str, select: str, filters: dict[str, str], order: str | None) -> str:
        query = {"select": select}
        query.update(filters)
        if order:
            query["order"] = order

        return f"{self.api_base_url}/rest/v1/{table_name}?{urlencode(query)}"


class DiscoveryError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class ScriptDiscoveredCatalogConfig:
    id: str
    site_url: str
    source_type: str = SCRIPT_DISCOVERED_SOURCE_TYPE
    table_name: str = "channels"
    select: str = "*,categories(name)"
    filters: dict[str, str] | None = None
    order: str | None = "channel_number.asc"
    timeout: int = 30

    @classmethod
    def from_dict(cls, data: dict) -> "ScriptDiscoveredCatalogConfig":
        return cls(
            id=data["id"],
            site_url=data["site_url"],
            source_type=data.get("source_type", SCRIPT_DISCOVERED_SOURCE_TYPE),
            table_name=data.get("table_name", "channels"),
            select=data.get("select", "*,categories(name)"),
            filters=data.get("filters", {"is_active": "eq.true"}),
            order=data.get("order", "channel_number.asc"),
            timeout=int(data.get("timeout", 30)),
        )


def _fetch_text(session: requests.Session, url: str, timeout: int) -> str:
    response = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def discover_script_urls(site_url: str, html: str) -> list[str]:
    parser = ScriptParser()
    parser.feed(html)
    return [urljoin(site_url, src) for src in parser.scripts]


def extract_rest_catalog_config(js_content: str) -> tuple[list[str], list[str]]:
    api_base_urls = sorted(set(SUPABASE_URL_PATTERN.findall(js_content)))
    anon_keys = sorted(set(JWT_PATTERN.findall(js_content)))
    return api_base_urls, anon_keys


def discover_rest_catalog(
    site_url: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> DiscoveredRestCatalog:
    owns_session = session is None
    session = session or requests.Session()

    try:
        html = _fetch_text(session, site_url, timeout)
        script_urls = discover_script_urls(site_url, html)
        if not script_urls:
            raise DiscoveryError("No script tags with src were found")

        for script_url in script_urls:
            try:
                js_content = _fetch_text(session, script_url, timeout)
            except requests.RequestException as exc:
                logger.warning("Failed to inspect script url=%s error=%s", script_url, exc)
                continue

            api_base_urls, anon_keys = extract_rest_catalog_config(js_content)
            if api_base_urls and anon_keys:
                return DiscoveredRestCatalog(
                    site_url=site_url,
                    script_url=script_url,
                    api_base_url=api_base_urls[0],
                    anon_key=anon_keys[0],
                )

    finally:
        if owns_session:
            session.close()

    raise DiscoveryError("Could not find a REST catalog URL and anonymous API key")


def fetch_rest_catalog_rows(
    catalog: DiscoveredRestCatalog,
    table_name: str = "channels",
    select: str = "*,categories(name)",
    filters: dict[str, str] | None = None,
    order: str | None = "channel_number.asc",
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[dict]:
    owns_session = session is None
    session = session or requests.Session()
    filters = filters or {"is_active": "eq.true"}

    try:
        endpoint = catalog.endpoint(table_name, select, filters, order)
        response = session.get(
            endpoint,
            headers={
                "apikey": catalog.anon_key,
                "Authorization": f"Bearer {catalog.anon_key}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise DiscoveryError("REST catalog response is not a JSON list")
        return payload

    finally:
        if owns_session:
            session.close()


def _category_name(row: dict) -> str:
    categories = row.get("categories")
    if isinstance(categories, dict):
        return categories.get("name") or "web"
    return "web"


def _row_status(row: dict, stream_url: str | None) -> str:
    if not stream_url:
        return "offline"

    status = str(row.get("stream_status") or "active").casefold()
    if status in {"inactive", "offline", "down", "error"}:
        return "offline"

    return "resolved"


def _row_id(row: dict) -> str:
    value = (
        row.get("epg_slug")
        or row.get("slug")
        or row.get("channel_number")
        or row.get("id")
        or row.get("name")
    )
    return str(value)


def _row_tvg_id(row: dict) -> str | None:
    value = (
        row.get("tvg_id")
        or row.get("xmltv_id")
        or row.get("epg_id")
        or row.get("epg_slug")
    )
    return str(value) if value else None


def row_to_channel(
    row: dict,
    source_type: str,
    default_resolution: str = "best",
    id_prefix: str | None = None,
) -> Channel:
    stream_url = row.get("stream_url") or row.get("url")
    base_id = _row_id(row)
    channel_id = f"{id_prefix}.{base_id}" if id_prefix else base_id

    return Channel(
        id=channel_id,
        name=str(row.get("name") or base_id),
        source_url=str(row.get("source_url") or stream_url or ""),
        logo=str(row.get("logo_url") or row.get("logo") or ""),
        group=_category_name(row),
        source_type=source_type,
        tvg_id=_row_tvg_id(row),
        resolution=default_resolution,
        stream_url=stream_url,
        status=_row_status(row, stream_url),
        ttl_seconds=None,
    )


def load_config_resource() -> list[ScriptDiscoveredCatalogConfig]:
    resource = resources.files("live_stream_catalog.resources").joinpath(CONFIG_RESOURCE_NAME)
    if not resource.is_file():
        return []

    raw = resource.read_text(encoding="utf-8")
    import json

    return [ScriptDiscoveredCatalogConfig.from_dict(item) for item in json.loads(raw)]


def load_rest_catalog_channels(
    configs: list[ScriptDiscoveredCatalogConfig],
    default_resolution: str = "best",
    session: requests.Session | None = None,
    continue_on_error: bool = True,
) -> list[Channel]:
    owns_session = session is None
    session = session or requests.Session()
    channels: list[Channel] = []

    try:
        for config in configs:
            try:
                catalog = discover_rest_catalog(
                    config.site_url,
                    session=session,
                    timeout=config.timeout,
                )
                rows = fetch_rest_catalog_rows(
                    catalog,
                    table_name=config.table_name,
                    select=config.select,
                    filters=config.filters,
                    order=config.order,
                    session=session,
                    timeout=config.timeout,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to load script-discovered catalog id=%s url=%s error=%s",
                    config.id,
                    config.site_url,
                    exc,
                )
                if not continue_on_error:
                    raise
                continue

            channels.extend(
                row_to_channel(
                    row,
                    source_type=config.source_type,
                    default_resolution=default_resolution,
                    id_prefix=config.id,
                )
                for row in rows
            )

    finally:
        if owns_session:
            session.close()

    return channels


def load_configured_rest_catalogs(
    default_resolution: str = "best",
    continue_on_error: bool = True,
) -> list[Channel]:
    return load_rest_catalog_channels(
        load_config_resource(),
        default_resolution=default_resolution,
        continue_on_error=continue_on_error,
    )
