"""Create durable Agent Run events for audit and replay."""

from alembic import op
import sqlalchemy as sa

revision = "20260826_05"
down_revision = "20260826_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_run_events_run_sequence",
        ),
    )
    op.create_index(
        "ix_run_events_client_run_sequence",
        "run_events",
        ["client_id", "run_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_events_client_run_sequence", table_name="run_events")
    op.drop_table("run_events")
