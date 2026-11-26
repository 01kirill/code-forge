from alembic import op

revision = "0002_contest_retention"
down_revision = "0001_contest"


def upgrade() -> None:
    op.create_index("outbox_published", "outbox", ["published_at"])


def downgrade() -> None:
    op.drop_index("outbox_published", table_name="outbox")
