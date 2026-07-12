import unittest

from live_stream_catalog.models import Channel
from live_stream_catalog.sources.loader import _deduplicate


class LoaderTest(unittest.TestCase):
    def test_preserves_same_id_with_different_source_urls(self):
        channels = [
            Channel(
                id="same.tv",
                name="Primary",
                source_url="https://example.test/primary",
                logo="",
                group="general",
                source_type="youtube",
            ),
            Channel(
                id="same.tv",
                name="Alternative",
                source_url="https://example.test/alternative",
                logo="",
                group="general",
                source_type="youtube",
            ),
        ]

        result = _deduplicate(channels)

        self.assertEqual(result, channels)

    def test_removes_duplicate_source_urls(self):
        channels = [
            Channel(
                id="first.tv",
                name="First",
                source_url="https://example.test/live",
                logo="",
                group="general",
                source_type="youtube",
            ),
            Channel(
                id="second.tv",
                name="Second",
                source_url="https://example.test/live",
                logo="",
                group="general",
                source_type="youtube",
            ),
        ]

        result = _deduplicate(channels)

        self.assertEqual(result, [channels[0]])


if __name__ == "__main__":
    unittest.main()
