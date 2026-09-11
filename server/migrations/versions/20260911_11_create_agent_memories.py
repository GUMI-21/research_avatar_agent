"""Create lightweight client-scoped Agent memories."""

from alembic import op
import sqlalchemy as sa

revision = "20260911_11"
down_revision = "20260903_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_agent_memories_client_agent", "agent_memories", ["client_id", "agent_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_memories_client_agent", table_name="agent_memories")
    op.drop_table("agent_memories")
