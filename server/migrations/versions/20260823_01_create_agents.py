"""Create the client-scoped agents table."""

from alembic import op
import sqlalchemy as sa

revision = "20260823_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column(
            "runtime", sa.String(length=32), server_default="native", nullable=False
        ),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "name", name="uq_agents_client_name"),
    )
    op.create_index("ix_agents_client_id", "agents", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_client_id", table_name="agents")
    op.drop_table("agents")
