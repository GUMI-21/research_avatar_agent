"""Store client-scoped Agent Skill bindings."""

from alembic import op
import sqlalchemy as sa

revision = "20260919_19"
down_revision = "20260917_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_skills",
        sa.Column("client_id", sa.String(64), primary_key=True),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("skill_id", sa.String(64), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("agent_skills")
