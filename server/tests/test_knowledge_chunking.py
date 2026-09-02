"""Tests for heading-aware Markdown chunking and citation locations."""

import unittest
from hashlib import sha256

from app.adapters.knowledge import chunk_markdown


class KnowledgeChunkingTest(unittest.TestCase):
    def test_frontmatter_headings_and_original_lines_are_preserved(self) -> None:
        chunks = chunk_markdown(
            """---
title: RAG
---
# 检索
第一段

## 混合检索
第二段
第三段
"""
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].heading_path, ("检索",))
        self.assertEqual((chunks[0].start_line, chunks[0].end_line), (5, 5))
        self.assertEqual(chunks[1].heading_path, ("检索", "混合检索"))
        self.assertEqual((chunks[1].start_line, chunks[1].end_line), (8, 9))
        self.assertEqual(
            chunks[1].content_hash,
            sha256("第二段\n第三段".encode()).hexdigest(),
        )

    def test_size_limit_splits_lines_and_code_heading_is_not_a_section(self) -> None:
        chunks = chunk_markdown(
            "# Code\nline-one\n```python\n# not heading\n```\nline-two",
            max_chars=20,
        )

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.heading_path == ("Code",) for chunk in chunks))
        self.assertIn("# not heading", "\n".join(chunk.content for chunk in chunks))

    def test_long_lines_are_split_and_inline_image_data_is_not_indexed(self) -> None:
        chunks = chunk_markdown(
            "# Note\n![x](data:image/png;base64,abcdef)\n123456789",
            max_chars=4,
        )

        self.assertEqual([chunk.content for chunk in chunks], ["1234", "5678", "9"])
        self.assertTrue(all(chunk.start_line == 3 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
