import os
import unittest

import requests

from live_stream_catalog.sources.script_discovered_catalog import (
    discover_rest_catalog,
    fetch_rest_catalog_rows,
)


DEFAULT_CATALOG_SITE_URL = "https://batistaplay.net/"


class ScriptDiscoveredCatalogIntegrationTest(unittest.TestCase):
    def test_fetches_rows_from_script_discovered_catalog_site(self):
        site_url = os.environ.get("SCRIPT_DISCOVERED_CATALOG_URL", DEFAULT_CATALOG_SITE_URL)

        with requests.Session() as session:
            catalog = discover_rest_catalog(site_url, session=session)
            rows = fetch_rest_catalog_rows(catalog, session=session)

        self.assertGreater(len(rows), 0)
        self.assertIsInstance(rows[0], dict)
        self.assertIn("name", rows[0])


if __name__ == "__main__":
    unittest.main()
