"""Create client-scoped Agent conversation sessions."""

from alembic import op
import sqlalchemy as sa

revision = "20260825_02"
down_revision = "20260823_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column(
            "title",
            sa.String(length=160),
            server_default="New conversation",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_agent_id", "sessions", ["agent_id"])
    op.create_index(
        "ix_sessions_client_created",
        "sessions",
        ["client_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_client_created", table_name="sessions")
    op.drop_index("ix_sessions_agent_id", table_name="sessions")
    op.drop_table("sessions")
