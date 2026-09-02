"""Create replaceable embedding storage for knowledge chunks."""

from alembic import op
import sqlalchemy as sa

revision = "20260902_09"
down_revision = "20260902_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunk_embeddings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "dimensions > 0", name="ck_knowledge_embeddings_dimensions"
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["knowledge_chunks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            name="uq_knowledge_embeddings_chunk_model",
        ),
    )
    op.create_index(
        "ix_knowledge_embeddings_client_source_model",
        "knowledge_chunk_embeddings",
        ["client_id", "source_id", "provider", "model"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_embeddings_client_source_model",
        table_name="knowledge_chunk_embeddings",
    )
    op.drop_table("knowledge_chunk_embeddings")
