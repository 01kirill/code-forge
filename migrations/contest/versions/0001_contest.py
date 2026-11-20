from alembic import op

revision = "0001_contest"
down_revision = None


def upgrade() -> None:
    for statement in (
        """
        CREATE TABLE users_cache (
            id uuid PRIMARY KEY, name text NOT NULL, version integer NOT NULL
        )
        """,
        """
        CREATE TABLE contests (
            id uuid PRIMARY KEY,
            owner_id uuid NOT NULL REFERENCES users_cache(id) ON DELETE RESTRICT,
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
            description text NOT NULL,
            duration integer NOT NULL CHECK (duration BETWEEN 5 AND 600),
            invite varchar(22) NOT NULL UNIQUE CHECK (length(invite)=22),
            state text NOT NULL DEFAULT 'draft'
              CHECK (state IN ('draft','countdown','running','finished')),
            start_at timestamptz, end_at timestamptz,
            finished_at timestamptz, final_rows jsonb,
            version integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE participants (
            contest_id uuid REFERENCES contests(id) ON DELETE CASCADE,
            user_id uuid REFERENCES users_cache(id) ON DELETE RESTRICT,
            joined_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (contest_id,user_id)
        )
        """,
        """
        CREATE TABLE contest_problems (
            contest_id uuid REFERENCES contests(id) ON DELETE CASCADE,
            label char(1) NOT NULL CHECK (label BETWEEN 'A' AND 'Z'),
            task_id text NOT NULL, task_version text NOT NULL,
            snapshot jsonb NOT NULL,
            PRIMARY KEY (contest_id,label),
            UNIQUE (contest_id,task_id)
        )
        """,
        """
        CREATE TABLE contest_submissions (
            id uuid PRIMARY KEY,
            contest_id uuid NOT NULL, user_id uuid NOT NULL, label char(1) NOT NULL,
            language text NOT NULL, code text NOT NULL,
            submitted_at timestamptz NOT NULL,
            dispatch_after timestamptz NOT NULL,
            result jsonb,
            FOREIGN KEY (contest_id,user_id)
              REFERENCES participants(contest_id,user_id) ON DELETE CASCADE,
            FOREIGN KEY (contest_id,label)
              REFERENCES contest_problems(contest_id,label) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE standings_cells (
            contest_id uuid NOT NULL, user_id uuid NOT NULL, label char(1) NOT NULL,
            failures integer NOT NULL, accepted_at timestamptz,
              penalty integer NOT NULL,
            PRIMARY KEY (contest_id,user_id,label),
            FOREIGN KEY (contest_id,user_id)
              REFERENCES participants(contest_id,user_id) ON DELETE CASCADE,
            FOREIGN KEY (contest_id,label)
              REFERENCES contest_problems(contest_id,label) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE outbox (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, exchange text NOT NULL,
            routing_key text NOT NULL, body jsonb NOT NULL, published_at timestamptz
        )
        """,
        "CREATE INDEX contest_start_due ON contests(start_at) WHERE state='countdown'",
        "CREATE INDEX contest_end_due ON contests(end_at) WHERE finished_at IS NULL",
        "CREATE INDEX participant_history ON participants(user_id, joined_at DESC)",
        "CREATE INDEX submission_room_time ON contest_submissions(contest_id, "
        "submitted_at)",
        "CREATE INDEX submission_cell ON contest_submissions"
        "(contest_id,user_id,label,submitted_at)",
        "CREATE INDEX submission_retry ON contest_submissions(dispatch_after) "
        "WHERE result IS NULL",
        "CREATE INDEX outbox_pending ON outbox(id) WHERE published_at IS NULL",
    ):
        op.execute(statement)


def downgrade() -> None:
    for table in (
        "outbox",
        "standings_cells",
        "contest_submissions",
        "contest_problems",
        "participants",
        "contests",
        "users_cache",
    ):
        op.drop_table(table)
