"""Persist encrypted per-workspace Google OAuth credentials."""

from alembic import op
import sqlalchemy as sa

revision = "20260917_18"
down_revision = "20260913_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "google_oauth_credentials",
        sa.Column("client_id", sa.String(64), primary_key=True),
        sa.Column("account_email", sa.String(320), nullable=True),
        sa.Column("scopes_json", sa.Text(), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("google_oauth_credentials")