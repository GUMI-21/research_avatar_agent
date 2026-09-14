"""Tests for file tools governed by the Server process permissions."""

import tempfile
import unittest
from pathlib import Path

from app.tools import ToolContext, create_file_tool_registry


class FileToolsTest(unittest.IsolatedAsyncioTestCase):
    async def test_lists_and_reads_files_under_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes").mkdir()
            (root / "notes" / "hello.md").write_text("hello world", encoding="utf-8")
            registry = create_file_tool_registry(root)
            context = ToolContext("client-a", "agent-a")

            listing = await registry.execute(
                "list_files", context, {"path": "notes"}
            )
            content = await registry.execute(
                "read_text_file", context,
                {"path": "notes/hello.md", "max_chars": 5},
            )

            self.assertTrue(listing.content.endswith("notes/hello.md"))
            self.assertEqual(content.content, "hello")
            self.assertTrue(content.metadata["truncated"])

    async def test_reads_absolute_path_outside_default_directory(self) -> None:
        with (
            tempfile.TemporaryDirectory() as default_directory,
            tempfile.TemporaryDirectory() as other_directory,
        ):
            outside = Path(other_directory) / "outside.txt"
            outside.write_text("allowed by OS", encoding="utf-8")
            registry = create_file_tool_registry(Path(default_directory))

            result = await registry.execute(
                "read_text_file",
                ToolContext("client-a", "agent-a"),
                {"path": str(outside)},
            )

            self.assertEqual(result.content, "allowed by OS")

    async def test_markdown_write_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            registry = create_file_tool_registry()
            context = ToolContext("client-a", "agent-a")
            arguments = {"path": str(path), "content": "# Updated"}

            with self.assertRaises(PermissionError):
                await registry.execute("write_markdown", context, arguments)
            self.assertFalse(path.exists())

            result = await registry.execute(
                "write_markdown", context, arguments, approved=True
            )
            self.assertEqual(path.read_text(encoding="utf-8"), "# Updated")
            self.assertEqual(result.metadata["path"], str(path))

if __name__ == "__main__":
    unittest.main()
