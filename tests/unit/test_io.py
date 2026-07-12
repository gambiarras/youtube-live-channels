import tempfile
import unittest
from pathlib import Path

from live_stream_catalog.io import load_channels_file, write_json_atomic


class JsonStoreTest(unittest.TestCase):
    def test_load_channels_file_returns_empty_for_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.json"

            self.assertEqual(load_channels_file(path), [])

    def test_write_json_atomic_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "payload.json"

            write_json_atomic(path, {"ok": True})

            self.assertEqual(path.read_text(encoding="utf-8"), '{\n  "ok": true\n}')


if __name__ == "__main__":
    unittest.main()
