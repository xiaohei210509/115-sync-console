from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import config


class ConfigTests(unittest.TestCase):
    def test_excluded_path_matches_directory_and_descendants(self):
        original = config.EXCLUDED_PREFIXES
        try:
            config.EXCLUDED_PREFIXES = ("Media/Downloads",)
            self.assertTrue(config.is_excluded("Media/Downloads"))
            self.assertTrue(config.is_excluded("Media/Downloads/file.mkv"))
            self.assertFalse(config.is_excluded("Media/Download"))
        finally:
            config.EXCLUDED_PREFIXES = original

    def test_strip_remote_root(self):
        original = config.ROOT_NAME
        try:
            config.ROOT_NAME = "Media"
            self.assertEqual(config.strip_remote_root("Media/Show/E01.mkv"), "Show/E01.mkv")
            self.assertEqual(config.strip_remote_root("Other/file.mkv"), "Other/file.mkv")
        finally:
            config.ROOT_NAME = original


if __name__ == "__main__":
    unittest.main()
