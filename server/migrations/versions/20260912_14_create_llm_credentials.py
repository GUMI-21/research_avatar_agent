"""Persist encrypted per-workspace provider credentials."""

from alembic import op
import sqlalchemy as sa

revision = "20260912_14"
down_revision = "20260911_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_credentials",
        sa.Column("client_id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), primary_key=True),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_credentials")
