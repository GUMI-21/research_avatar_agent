"""Create client-scoped visible conversation messages."""

from alembic import op
import sqlalchemy as sa

revision = "20260826_03"
down_revision = "20260825_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name="ck_messages_role",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "sequence",
            name="uq_messages_session_sequence",
        ),
    )
    op.create_index("ix_messages_run_id", "messages", ["run_id"])
    op.create_index(
        "ix_messages_client_session_sequence",
        "messages",
        ["client_id", "session_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_client_session_sequence", table_name="messages")
    op.drop_index("ix_messages_run_id", table_name="messages")
    op.drop_table("messages")
