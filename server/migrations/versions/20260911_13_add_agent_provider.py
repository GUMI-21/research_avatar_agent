"""Store the LLM provider selected for each Agent."""

from alembic import op
import sqlalchemy as sa

revision = "20260911_13"
down_revision = "20260911_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("provider", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "provider")
