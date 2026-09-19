"""Record the Skills injected into each Agent Run."""

from alembic import op
import sqlalchemy as sa

revision = "20260919_20"
down_revision = "20260919_19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("skill_versions", sa.JSON(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("runs", "skill_versions")
