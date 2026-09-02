"""Create a trigger-maintained FTS5 index for knowledge chunks."""

from alembic import op

revision = "20260902_08"
down_revision = "20260901_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE VIRTUAL TABLE knowledge_chunks_fts USING fts5(
        chunk_id UNINDEXED, client_id UNINDEXED, source_id UNINDEXED,
        document_id UNINDEXED, heading_path, content, tokenize='trigram'
        )"""
    )
    op.execute(
        """CREATE TRIGGER knowledge_chunks_fts_insert AFTER INSERT ON knowledge_chunks
        BEGIN
          INSERT INTO knowledge_chunks_fts
          (chunk_id, client_id, source_id, document_id, heading_path, content)
          VALUES (new.id, new.client_id, new.source_id, new.document_id,
                  new.heading_path, new.content);
        END"""
    )
    op.execute(
        """CREATE TRIGGER knowledge_chunks_fts_delete AFTER DELETE ON knowledge_chunks
        BEGIN
          DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.id;
        END"""
    )
    op.execute(
        """CREATE TRIGGER knowledge_chunks_fts_update AFTER UPDATE ON knowledge_chunks
        BEGIN
          DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.id;
          INSERT INTO knowledge_chunks_fts
          (chunk_id, client_id, source_id, document_id, heading_path, content)
          VALUES (new.id, new.client_id, new.source_id, new.document_id,
                  new.heading_path, new.content);
        END"""
    )
    op.execute(
        """INSERT INTO knowledge_chunks_fts
        (chunk_id, client_id, source_id, document_id, heading_path, content)
        SELECT id, client_id, source_id, document_id, heading_path, content
        FROM knowledge_chunks"""
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER knowledge_chunks_fts_update")
    op.execute("DROP TRIGGER knowledge_chunks_fts_delete")
    op.execute("DROP TRIGGER knowledge_chunks_fts_insert")
    op.execute("DROP TABLE knowledge_chunks_fts")
