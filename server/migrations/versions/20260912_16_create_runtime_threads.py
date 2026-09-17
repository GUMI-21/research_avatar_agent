"""Create client-scoped external runtime thread bindings."""

from alembic import op
import sqlalchemy as sa

revision = "20260912_16"
down_revision = "20260912_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_threads",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("runtime", sa.String(64), nullable=False),
        sa.Column("external_thread_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_id", "session_id", "agent_id", "runtime",
            name="uq_runtime_threads_scope",
        ),
    )
    op.create_index(
        "ix_runtime_threads_client_id", "runtime_threads", ["client_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_runtime_threads_client_id", table_name="runtime_threads")
    op.drop_table("runtime_threads")
