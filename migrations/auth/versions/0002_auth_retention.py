from alembic import op

revision = "0002_auth_retention"
down_revision = "0001_auth"


def upgrade() -> None:
    op.create_index("refresh_tokens_expiry", "refresh_tokens", ["expires_at"])
    op.create_index("outbox_published", "outbox", ["published_at"])


def downgrade() -> None:
    op.drop_index("outbox_published", table_name="outbox")
    op.drop_index("refresh_tokens_expiry", table_name="refresh_tokens")
