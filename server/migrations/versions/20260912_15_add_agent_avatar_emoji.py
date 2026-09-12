"""Add a display Emoji to each Agent."""

from alembic import op
import sqlalchemy as sa

revision = "20260912_15"
down_revision = "20260912_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("avatar_emoji", sa.String(16), nullable=False, server_default="🤖"),
    )


def downgrade() -> None:
    op.drop_column("agents", "avatar_emoji")
