import unittest

from live_stream_catalog.sources.script_discovered_catalog import (
    DiscoveredRestCatalog,
    discover_script_urls,
    extract_rest_catalog_config,
    row_to_channel,
)


class ScriptDiscoveredCatalogTest(unittest.TestCase):
    def test_discovers_absolute_script_urls(self):
        html = """
        <html>
          <head>
            <script src="/assets/app.js"></script>
            <script src="https://cdn.example.test/vendor.js"></script>
          </head>
        </html>
        """

        self.assertEqual(
            discover_script_urls("https://example.test/", html),
            [
                "https://example.test/assets/app.js",
                "https://cdn.example.test/vendor.js",
            ],
        )

    def test_extracts_rest_catalog_configuration_from_js(self):
        key = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9.signature_part"
        js_content = f"""
        const url = "https://project-ref.supabase.co";
        const anon = "{key}";
        """

        api_base_urls, anon_keys = extract_rest_catalog_config(js_content)

        self.assertEqual(api_base_urls, ["https://project-ref.supabase.co"])
        self.assertEqual(anon_keys, [key])

    def test_builds_rest_endpoint_with_encoded_query(self):
        catalog = DiscoveredRestCatalog(
            site_url="https://example.test/",
            script_url="https://example.test/assets/app.js",
            api_base_url="https://project-ref.supabase.co",
            anon_key="token",
        )

        endpoint = catalog.endpoint(
            table_name="channels",
            select="*,categories(name)",
            filters={"is_active": "eq.true"},
            order="channel_number.asc",
        )

        self.assertEqual(
            endpoint,
            "https://project-ref.supabase.co/rest/v1/channels"
            "?select=%2A%2Ccategories%28name%29"
            "&is_active=eq.true"
            "&order=channel_number.asc",
        )

    def test_maps_catalog_row_to_channel(self):
        channel = row_to_channel(
            {
                "id": "sample",
                "name": "Sample Channel",
                "stream_url": "https://media.example.test/live.m3u8",
                "logo_url": "https://media.example.test/logo.png",
                "categories": {"name": "news"},
            },
            source_type="script_discovered",
        )

        self.assertEqual(channel.id, "sample")
        self.assertEqual(channel.name, "Sample Channel")
        self.assertEqual(channel.source_url, "https://media.example.test/live.m3u8")
        self.assertEqual(channel.stream_url, "https://media.example.test/live.m3u8")
        self.assertEqual(channel.logo, "https://media.example.test/logo.png")
        self.assertEqual(channel.group, "news")
        self.assertEqual(channel.source_type, "script_discovered")
        self.assertEqual(channel.status, "resolved")
        self.assertIsNone(channel.ttl_seconds)


if __name__ == "__main__":
    unittest.main()
