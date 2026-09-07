"""Tests for the non-blocking local embedding adapter."""

import unittest
from math import isclose
from unittest.mock import MagicMock, patch

from app.adapters.knowledge import FastEmbedAdapter


class FastEmbedAdapterTest(unittest.IsolatedAsyncioTestCase):
    @patch("app.adapters.knowledge.embedding.TextEmbedding")
    async def test_query_and_documents_use_distinct_fastembed_paths(
        self,
        text_embedding: MagicMock,
    ) -> None:
        engine = text_embedding.return_value
        engine.passage_embed.return_value = [[0.1, 0.2], [0.3, 0.4]]
        engine.query_embed.return_value = [[0.5, 0.6]]
        adapter = FastEmbedAdapter(model="test-model", dimensions=2)

        documents = await adapter.embed_documents(["文档一", "文档二"])
        query = await adapter.embed_query("查询")

        self.assertTrue(isclose(sum(value * value for value in documents[0]), 1.0))
        self.assertTrue(isclose(sum(value * value for value in query), 1.0))
        engine.passage_embed.assert_called_once_with(["文档一", "文档二"])
        engine.query_embed.assert_called_once_with("查询")
        text_embedding.assert_called_once_with(
            model_name="test-model",
            cache_dir=None,
            lazy_load=True,
        )


if __name__ == "__main__":
    unittest.main()
