"""Tests for reciprocal-rank fusion in hybrid knowledge retrieval."""

import unittest

from app.repositories import KnowledgeChunkHit
from app.services import KnowledgeRetrievalService


def hit(chunk_id: str, score: float) -> KnowledgeChunkHit:
    return KnowledgeChunkHit(
        chunk_id=chunk_id,
        document_id="document",
        title=chunk_id,
        relative_path=f"{chunk_id}.md",
        heading_path=(),
        content=chunk_id,
        start_line=1,
        end_line=1,
        score=score,
    )


class KnowledgeHybridRetrievalTest(unittest.TestCase):
    def test_shared_hit_is_promoted_and_results_are_limited(self) -> None:
        results = KnowledgeRetrievalService._reciprocal_rank_fusion(
            (
                [hit("a", 10), hit("b", 5)],
                [hit("b", 0.9), hit("c", 0.8)],
            ),
            limit=2,
        )

        self.assertEqual([result.chunk_id for result in results], ["b", "a"])
        self.assertGreater(results[0].score, results[1].score)


if __name__ == "__main__":
    unittest.main()
