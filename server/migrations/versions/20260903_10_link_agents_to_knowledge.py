"""Link Agent configurations to client-scoped knowledge sources."""

from alembic import op
import sqlalchemy as sa

revision = "20260903_10"
down_revision = "20260902_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_knowledge_sources",
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("client_id", "agent_id", "source_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_knowledge_sources")
