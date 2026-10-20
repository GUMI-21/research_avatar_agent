"""Create one client-scoped teaching state per conversation."""

from alembic import op
import sqlalchemy as sa

revision = "20261020_21"
down_revision = "20260919_20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teaching_session_states",
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("course_id", sa.String(64), nullable=False),
        sa.Column("lesson_id", sa.String(64), nullable=False),
        sa.Column("course_version", sa.String(64), nullable=False),
        sa.Column("completed_turns", sa.Integer(), server_default="0", nullable=False),
        sa.Column("state_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("completed_turns >= 0", name="ck_teaching_turns_nonnegative"),
        sa.CheckConstraint("state_version >= 1", name="ck_teaching_version_positive"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_teaching_sessions_client", "teaching_session_states", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_teaching_sessions_client", table_name="teaching_session_states")
    op.drop_table("teaching_session_states")
