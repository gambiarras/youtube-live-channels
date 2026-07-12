"""
$description Kick, a gaming livestreaming platform
$url kick.com
$type live, vod
"""

import logging
import re

import cloudscraper
from streamlink import Streamlink
from streamlink.exceptions import PluginError
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.plugin.api import validate
from streamlink.stream.hls import HLSStream


log = logging.getLogger(__name__)


@pluginmatcher(
    re.compile(
        r"https?://(?:www\.)?kick\.com/(?!(?:video|categories|search|auth)(?:[/?#]|$))(?P<channel>[\w_-]+)$",
    ),
    name="live",
)
@pluginmatcher(
    re.compile(
        r"https?://(?:www\.)?kick\.com/video/(?P<video_id>[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12})",
    ),
    name="vod",
)
@pluginmatcher(
    re.compile(
        r"https?://(?:www\.)?kick\.com/(?!(?:video|categories|search|auth)(?:[/?#]|$))(?P<channel>[\w_-]+)\?clip=(?P<clip_id>[\w_]+)$",
    ),
    name="clip",
)
class KICK(Plugin):
    def _get_streams(self):
        api_base_url = "https://kick.com/api"

        live_schema = validate.Schema(
            validate.parse_json(),
            {
                "playback_url": validate.url(path=validate.endswith(".m3u8")),
                "livestream": {
                    "is_live": True,
                    "id": int,
                    "session_title": str,
                    "categories": [{"name": str}],
                },
                "user": {"username": str},
            },
            validate.union_get(
                "playback_url",
                ("livestream", "id"),
                ("user", "username"),
                ("livestream", "session_title"),
                ("livestream", "categories", 0, "name"),
            ),
        )

        video_schema = validate.Schema(
            validate.parse_json(),
            {
                "source": validate.url(path=validate.endswith(".m3u8")),
                "id": int,
                "livestream": {
                    "channel": {"user": {"username": str}},
                    "session_title": str,
                    "categories": [{"name": str}],
                },
            },
            validate.union_get(
                "source",
                "id",
                ("livestream", "channel", "user", "username"),
                ("livestream", "session_title"),
                ("livestream", "categories", 0, "name"),
            ),
        )

        clip_schema = validate.Schema(
            validate.parse_json(),
            {
                "clip": {
                    "video_url": validate.url(path=validate.endswith(".m3u8")),
                    "id": str,
                    "channel": {"username": str},
                    "title": str,
                    "category": {"name": str},
                },
            },
            validate.union_get(
                ("clip", "video_url"),
                ("clip", "id"),
                ("clip", "channel", "username"),
                ("clip", "title"),
                ("clip", "category", "name"),
            ),
        )

        live = self.matches["live"]
        vod = self.matches["vod"]
        clip = self.matches["clip"]

        scraper = cloudscraper.create_scraper()

        try:
            response = scraper.get(
                "{0}/{1}/{2}".format(
                    api_base_url,
                    *(
                        ["v1/channels", self.match["channel"]]
                        if live
                        else (
                            ["v1/video", self.match["video_id"]]
                            if vod
                            else ["v2/clips", self.match["clip_id"]]
                        )
                    )
                ),
                timeout=20,
            )
            response.raise_for_status()

            schema = live_schema if live else (video_schema if vod else clip_schema)
            url, self.id, self.author, self.title, self.category = schema.validate(response.text)

        except (PluginError, TypeError, ValueError) as err:
            log.debug("Kick plugin validation failed: %s", err)
            return None
        except Exception as err:
            log.debug("Kick API request failed: %s", err)
            return None
        finally:
            scraper.close()

        if live or vod:
            try:
                return HLSStream.parse_variant_playlist(self.session, url)
            except Exception as err:
                log.debug("Kick variant playlist parsing failed, falling back to direct HLS: %s", err)
                return {"live": HLSStream(self.session, url)}

        if clip and self.author.casefold() == self.match["channel"].casefold():
            return {"source": HLSStream(self.session, url)}

        return None


__plugin__ = KICK


def register_kick_plugin(session: Streamlink) -> None:
    session.plugins.update({"kick": KICK})