"""Tests for Markdown and Obsidian relationship parsing."""

import unittest

from app.adapters.knowledge import MarkdownParseError, parse_markdown


class KnowledgeMarkdownTest(unittest.TestCase):
    def test_parse_metadata_links_and_images(self) -> None:
        parsed = parse_markdown(
            "notes/rag.md",
            """---
title: 个人知识库
tags: [RAG, 中文]
---
# ignored heading
关联 [[Agent 编排|编排]]、[[索引#混合检索]] 和 [[Agent 编排]]。
![[assets/流程图.png|600]]
![架构图](images/architecture.webp)
""",
        )

        self.assertEqual(parsed.title, "个人知识库")
        self.assertEqual(parsed.frontmatter["tags"], ["RAG", "中文"])
        self.assertEqual(parsed.note_links, ("Agent 编排", "索引#混合检索"))
        self.assertEqual(
            parsed.asset_links,
            ("assets/流程图.png", "images/architecture.webp"),
        )

    def test_title_falls_back_to_heading_then_file_name(self) -> None:
        self.assertEqual(parse_markdown("a.md", "# 标题\n正文").title, "标题")
        self.assertEqual(parse_markdown("folder/file.md", "正文").title, "file")

    def test_invalid_frontmatter_is_rejected(self) -> None:
        with self.assertRaises(MarkdownParseError):
            parse_markdown("invalid.md", "---\ntags: [broken\n---\nbody")
        with self.assertRaises(MarkdownParseError):
            parse_markdown("invalid.md", "---\n- item\n---\nbody")


if __name__ == "__main__":
    unittest.main()
