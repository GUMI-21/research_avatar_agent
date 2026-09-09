"""Tests for safe and deterministic Markdown discovery."""

import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from app.adapters.knowledge import scan_markdown_files


class KnowledgeFilesystemTest(unittest.TestCase):
    def test_scan_hashes_markdown_and_ignores_internal_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "vault"
            nested = root / "topics"
            ignored = root / ".obsidian"
            nested.mkdir(parents=True)
            ignored.mkdir()
            (root / "index.md").write_text("# 首页", encoding="utf-8")
            (nested / "rag.MD").write_text("混合检索", encoding="utf-8")
            (root / "image.png").write_bytes(b"image")
            (ignored / "plugin.md").write_text("internal", encoding="utf-8")

            scanned = scan_markdown_files(root)

        self.assertEqual(
            [item.relative_path for item in scanned],
            ["index.md", "topics/rag.MD"],
        )
        self.assertEqual(
            scanned[0].content_hash,
            sha256("# 首页".encode()).hexdigest(),
        )
        self.assertGreater(scanned[0].size_bytes, 0)

    def test_scan_does_not_follow_file_symlink_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            root = base / "vault"
            root.mkdir()
            outside = base / "private.md"
            outside.write_text("private", encoding="utf-8")
            try:
                (root / "linked.md").symlink_to(outside)
                (root / "broken.md").symlink_to(base / "missing.md")
            except OSError as error:
                # Windows requires Developer Mode or the symlink privilege.
                if getattr(error, "winerror", None) == 1314:
                    self.skipTest("Windows user lacks symbolic-link privilege")
                raise

            scanned = scan_markdown_files(root)

        self.assertEqual(scanned, [])


if __name__ == "__main__":
    unittest.main()
