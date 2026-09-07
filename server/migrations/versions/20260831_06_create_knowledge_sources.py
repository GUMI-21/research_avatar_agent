"""Create knowledge sources and imported Markdown documents."""

from alembic import op
import sqlalchemy as sa

revision = "20260831_06"
down_revision = "20260826_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "source_type",
            sa.String(length=16),
            server_default="obsidian",
            nullable=False,
        ),
        sa.Column("root_path", sa.String(length=2048), nullable=False),
        sa.Column(
            "sync_status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('obsidian', 'markdown')",
            name="ck_knowledge_sources_type",
        ),
        sa.CheckConstraint(
            "sync_status IN ('pending', 'syncing', 'ready', 'failed')",
            name="ck_knowledge_sources_sync_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_id",
            "name",
            name="uq_knowledge_sources_client_name",
        ),
    )
    op.create_index(
        "ix_knowledge_sources_client_created",
        "knowledge_sources",
        ["client_id", "created_at"],
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("relative_path", sa.String(length=1024), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("frontmatter", sa.JSON(), nullable=False),
        sa.Column("source_modified_at", sa.DateTime(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "relative_path",
            name="uq_knowledge_documents_source_path",
        ),
    )
    op.create_index(
        "ix_knowledge_documents_client_source_path",
        "knowledge_documents",
        ["client_id", "source_id", "relative_path"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_documents_client_source_path",
        table_name="knowledge_documents",
    )
    op.drop_table("knowledge_documents")
    op.drop_index(
        "ix_knowledge_sources_client_created",
        table_name="knowledge_sources",
    )
    op.drop_table("knowledge_sources")
