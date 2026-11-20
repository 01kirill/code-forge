from alembic import op

revision = "0001_auth"
down_revision = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("""
        CREATE TABLE users (
            id uuid PRIMARY KEY,
            email citext NOT NULL UNIQUE,
            name citext NOT NULL UNIQUE CHECK (length(name) BETWEEN 3 AND 32),
            password_hash text NOT NULL,
            role text NOT NULL DEFAULT 'student'
              CHECK (role IN ('student','teacher','admin')),
            timezone text NOT NULL DEFAULT 'UTC',
            active boolean NOT NULL DEFAULT true,
            version integer NOT NULL DEFAULT 1,
            sessions_after integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE refresh_tokens (
            digest char(64) PRIMARY KEY,
            sid uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            agent text NOT NULL,
            issued_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz
        )
    """)
    op.execute("CREATE INDEX refresh_user_session ON refresh_tokens(user_id, sid)")
    op.execute("""
        CREATE TABLE outbox (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            exchange text NOT NULL,
            routing_key text NOT NULL,
            body jsonb NOT NULL,
            published_at timestamptz
        )
    """)
    op.execute("CREATE INDEX outbox_pending ON outbox(id) WHERE published_at IS NULL")


def downgrade() -> None:
    for table in ("outbox", "refresh_tokens", "users"):
        op.drop_table(table)
    op.execute("DROP EXTENSION citext")
