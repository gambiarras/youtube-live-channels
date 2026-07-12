import unittest
from unittest.mock import patch

from live_stream_catalog.models import Channel
from live_stream_catalog.services.resolver import resolve_channels


class ResolverTest(unittest.TestCase):
    def test_resolves_pre_resolved_channels_without_streamlink_session(self):
        channel = Channel(
            id="ready.tv",
            name="Ready",
            source_url="https://media.example.test/live.m3u8",
            logo="",
            group="general",
            source_type="script_discovered",
            stream_url="https://media.example.test/live.m3u8?expires=4102444800",
            status="resolved",
        )

        with patch("live_stream_catalog.services.resolver.build_streamlink_session") as build_session:
            result = resolve_channels([channel], max_workers=6)

        build_session.assert_not_called()
        self.assertEqual(result[0].status, "resolved")
        self.assertEqual(result[0].expires_at, "2100-01-01T00:00:00+00:00")
        self.assertIsNotNone(result[0].ttl_seconds)

    def test_accepts_zero_workers_when_there_is_nothing_to_resolve(self):
        result = resolve_channels([], max_workers=0)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
