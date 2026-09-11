"""Create unique local workspace identities."""

from alembic import op
import sqlalchemy as sa

revision = "20260911_12"
down_revision = "20260911_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("username", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )
    connection = op.get_bind()
    for table in ("agents", "sessions", "messages", "runs", "knowledge_sources", "agent_memories"):
        connection.execute(sa.text(
            f"INSERT OR IGNORE INTO workspaces (username) SELECT DISTINCT lower(client_id) FROM {table}"
        ))


def downgrade() -> None:
    op.drop_table("workspaces")
