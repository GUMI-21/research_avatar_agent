"""Add an optional project workspace path to Agents."""

from alembic import op
import sqlalchemy as sa

revision = "20260913_17"
down_revision = "20260912_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("workspace_path", sa.String(1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "workspace_path")
