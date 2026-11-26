from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

import asyncpg
from asyncpg.pool import PoolConnectionProxy

from codeforge.common.broker import enqueue
from codeforge.common.contracts import Document, User, check_queue
from codeforge.contest.application.ports import CodeSubmission, ContestData, RoomDraft
from codeforge.contest.domain import Cell, State


class PostgresContests:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    @asynccontextmanager
    async def read(self) -> AsyncIterator[ContestData]:
        async with self.pool.acquire() as conn:
            yield PostgresContestData(conn)

    @asynccontextmanager
    async def transaction(
        self, *, snapshot: bool = False
    ) -> AsyncIterator[ContestData]:
        async with (
            self.pool.acquire() as conn,
            conn.transaction(isolation="repeatable_read" if snapshot else None),
        ):
            yield PostgresContestData(conn)


class PostgresContestData:
    def __init__(self, conn: PoolConnectionProxy) -> None:
        self.conn = conn

    async def clock(self) -> datetime:
        at: datetime = await self.conn.fetchval("SELECT clock_timestamp()")
        return at

    async def room(self, id_: UUID, *, lock: bool = False) -> Document | None:
        query = "SELECT * FROM contests WHERE id=$1"
        row = await self.conn.fetchrow(query + (" FOR UPDATE" if lock else ""), id_)
        return dict(row) if row is not None else None

    async def by_invite(self, token: str) -> Document | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM contests WHERE invite=$1 FOR UPDATE",
            token,
        )
        return dict(row) if row is not None else None

    async def rooms_for(self, user_id: UUID) -> list[Document]:
        rows = await self.conn.fetch(
            "SELECT c.*, statement_timestamp() AS server_time FROM contests c "
            "JOIN participants p ON p.contest_id=c.id "
            "WHERE p.user_id=$1 ORDER BY p.joined_at DESC LIMIT 100",
            user_id,
        )
        return [dict(row) for row in rows]

    async def create(
        self, id_: UUID, owner: UUID, data: RoomDraft, token: str
    ) -> Document:
        row = await self.conn.fetchrow(
            "INSERT INTO contests(id,owner_id,title,description,duration,invite) "
            "VALUES($1,$2,$3,$4,$5,$6) RETURNING *",
            id_,
            owner,
            data.title,
            data.description,
            data.duration,
            token,
        )
        assert row is not None
        return dict(row)

    async def edit(self, id_: UUID, data: RoomDraft) -> None:
        await self.conn.execute(
            "UPDATE contests SET title=$2,description=$3,duration=$4 WHERE id=$1",
            id_,
            data.title,
            data.description,
            data.duration,
        )

    async def set_invite(self, id_: UUID, token: str) -> None:
        await self.conn.execute("UPDATE contests SET invite=$2 WHERE id=$1", id_, token)

    async def start(self, id_: UUID, start: datetime, end: datetime) -> Document:
        row = await self.conn.fetchrow(
            "UPDATE contests SET state='countdown',start_at=$2,"
            "end_at=$3,version=version+1 WHERE id=$1 RETURNING *",
            id_,
            start,
            end,
        )
        assert row is not None
        return dict(row)

    async def due_rooms(self) -> list[Document]:
        rows = await self.conn.fetch(
            "SELECT * FROM contests c WHERE "
            "(state='countdown' AND start_at<=now()) OR "
            "(end_at<=now() AND (state<>'finished' OR "
            "(finished_at IS NULL AND NOT EXISTS(SELECT 1 FROM "
            "contest_submissions s "
            "WHERE s.contest_id=c.id AND s.result IS NULL)))) "
            "ORDER BY end_at LIMIT 20 FOR UPDATE SKIP LOCKED",
        )
        return [dict(row) for row in rows]

    async def set_state(self, id_: UUID, state: State) -> None:
        await self.conn.execute("UPDATE contests SET state=$2 WHERE id=$1", id_, state)

    async def finish(self, id_: UUID, at: datetime, results: list[Document]) -> None:
        await self.conn.execute(
            "UPDATE contests SET state='finished',finished_at=$2,final_rows=$3,"
            "version=version+1 WHERE id=$1",
            id_,
            at,
            results,
        )

    async def bump(self, id_: UUID) -> int:
        revision: int = await self.conn.fetchval(
            "UPDATE contests SET version=version+1 WHERE id=$1 RETURNING version",
            id_,
        )
        return revision

    async def known_user(self, user: User) -> None:
        await self.conn.execute(
            "INSERT INTO users_cache(id,name,version) VALUES($1,$2,$3) "
            "ON CONFLICT DO NOTHING",
            UUID(user.id),
            user.name,
            user.version,
        )

    async def sync_user(self, id_: UUID, name: str, version: int) -> None:
        await self.conn.execute(
            "INSERT INTO users_cache(id,name,version) VALUES($1,$2,$3) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,version=excluded.version "
            "WHERE users_cache.version < excluded.version",
            id_,
            name,
            version,
        )

    async def active_rooms_for(self, user: UUID) -> list[UUID]:
        rows = await self.conn.fetch(
            "SELECT p.contest_id FROM participants p JOIN contests c "
            "ON c.id=p.contest_id WHERE p.user_id=$1 AND c.finished_at IS NULL",
            user,
        )
        return [row["contest_id"] for row in rows]

    async def add_participant(self, contest: UUID, user: UUID) -> bool:
        return (
            await self.conn.execute(
                "INSERT INTO participants(contest_id,user_id) VALUES($1,$2) "
                "ON CONFLICT DO NOTHING",
                contest,
                user,
            )
            != "INSERT 0 0"
        )

    async def contains_participant(self, contest: UUID, user: UUID) -> bool:
        return bool(
            await self.conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM participants "
                "WHERE contest_id=$1 AND user_id=$2)",
                contest,
                user,
            )
        )

    async def members(self, contest: UUID) -> list[tuple[UUID, str]]:
        rows = await self.conn.fetch(
            "SELECT p.user_id, u.name FROM participants p JOIN users_cache u "
            "ON u.id=p.user_id WHERE p.contest_id=$1 ORDER BY u.name, u.id",
            contest,
        )
        return [(row["user_id"], row["name"]) for row in rows]

    async def problem_metadata(self, contest: UUID) -> list[Document]:
        rows = await self.conn.fetch(
            "SELECT label,task_id,snapshot->>'title' AS title "
            "FROM contest_problems WHERE contest_id=$1 ORDER BY label",
            contest,
        )
        return [dict(row) for row in rows]

    async def problem_snapshots(self, contest: UUID) -> list[Document]:
        rows = await self.conn.fetch(
            "SELECT label,snapshot FROM contest_problems "
            "WHERE contest_id=$1 ORDER BY label",
            contest,
        )
        return [row["snapshot"] | {"label": row["label"]} for row in rows]

    async def problem(self, contest: UUID, label: str) -> Document | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM contest_problems WHERE contest_id=$1 AND label=$2",
            contest,
            label,
        )
        return dict(row) if row is not None else None

    async def has_problems(self, contest: UUID) -> bool:
        return bool(
            await self.conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM contest_problems WHERE contest_id=$1)",
                contest,
            )
        )

    async def replace_problems(self, contest: UUID, snapshots: list[Document]) -> None:
        await self.conn.execute(
            "DELETE FROM contest_problems WHERE contest_id=$1", contest
        )
        await self.conn.executemany(
            "INSERT INTO contest_problems(contest_id,label,task_id,"
            "task_version,snapshot) "
            "VALUES($1,$2,$3,$4,$5)",
            [
                (contest, doc["label"], doc["task_id"], doc["version"], doc["snapshot"])
                for doc in snapshots
            ],
        )

    async def create_attempt(
        self,
        id_: UUID,
        contest: UUID,
        user: UUID,
        label: str,
        data: CodeSubmission,
        at: datetime,
        dispatch_after: datetime,
    ) -> Document:
        row = await self.conn.fetchrow(
            "INSERT INTO contest_submissions("
            "id,contest_id,user_id,label,language,code,submitted_at,dispatch_after"
            ") VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
            id_,
            contest,
            user,
            label,
            data.language,
            data.code,
            at,
            dispatch_after,
        )
        assert row is not None
        return dict(row)

    async def attempt(self, id_: UUID) -> Document | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM contest_submissions WHERE id=$1", id_
        )
        return dict(row) if row is not None else None

    async def attempts(
        self, contest: UUID, user: UUID, offset: int, id_: UUID | None
    ) -> list[Document]:
        rows = await self.conn.fetch(
            "SELECT * FROM contest_submissions WHERE contest_id=$1 AND user_id=$2 "
            "AND ($3::uuid IS NULL OR id=$3) ORDER BY submitted_at DESC,id "
            "LIMIT 30 OFFSET $4",
            contest,
            user,
            id_,
            offset,
        )
        return [dict(row) for row in rows]

    async def record_result(self, id_: UUID, result: Document) -> bool:
        return (
            await self.conn.fetchval(
                "UPDATE contest_submissions SET result=$2 "
                "WHERE id=$1 AND result IS NULL "
                "RETURNING id",
                id_,
                result,
            )
            is not None
        )

    async def verdicts(
        self, contest: UUID, user: UUID, label: str
    ) -> list[tuple[datetime, str]]:
        rows = await self.conn.fetch(
            "SELECT submitted_at,result->>'verdict' AS verdict "
            "FROM contest_submissions "
            "WHERE contest_id=$1 AND user_id=$2 AND label=$3 AND result IS NOT NULL "
            "ORDER BY submitted_at,id",
            contest,
            user,
            label,
        )
        return [(row["submitted_at"], row["verdict"]) for row in rows]

    async def pending(self, contest: UUID) -> int:
        count: int = await self.conn.fetchval(
            "SELECT count(*) FROM contest_submissions WHERE contest_id=$1 "
            "AND result IS NULL",
            contest,
        )
        return count

    async def reserve_submission(self) -> None:
        await self.conn.execute("SELECT pg_advisory_xact_lock(407721)")
        count, _ = await self.queue_status()
        check_queue(count)

    async def queue_status(self) -> tuple[int, datetime | None]:
        row = await self.conn.fetchrow(
            "SELECT count(*) AS depth, min(submitted_at) AS oldest "
            "FROM contest_submissions WHERE result IS NULL"
        )
        assert row is not None
        return row["depth"], row["oldest"]

    async def due_attempts(self) -> list[Document]:
        rows = await self.conn.fetch(
            "SELECT * FROM contest_submissions "
            "WHERE result IS NULL AND dispatch_after<=now() "
            "ORDER BY dispatch_after LIMIT 20 FOR UPDATE SKIP LOCKED",
        )
        return [dict(row) for row in rows]

    async def schedule_retry(self, attempt: UUID) -> None:
        await self.conn.execute(
            "UPDATE contest_submissions SET dispatch_after=now()+interval '45 seconds' "
            "WHERE id=$1",
            attempt,
        )

    async def cells(self, contest: UUID) -> list[tuple[UUID, str, Cell]]:
        rows = await self.conn.fetch(
            "SELECT * FROM standings_cells WHERE contest_id=$1",
            contest,
        )
        return [
            (
                row["user_id"],
                row["label"],
                Cell(row["failures"], row["accepted_at"], row["penalty"]),
            )
            for row in rows
        ]

    async def save_cell(
        self, contest: UUID, user: UUID, label: str, cell: Cell
    ) -> None:
        await self.conn.execute(
            "INSERT INTO standings_cells(contest_id,user_id,label,"
            "failures,accepted_at,penalty) VALUES($1,$2,$3,$4,$5,$6) "
            "ON CONFLICT(contest_id,user_id,label) DO UPDATE SET "
            "failures=excluded.failures,accepted_at=excluded.accepted_at,"
            "penalty=excluded.penalty",
            contest,
            user,
            label,
            cell.failures,
            cell.accepted_at,
            cell.penalty,
        )

    async def publish_later(self, key: str, event: Document) -> None:
        await enqueue(self.conn, key, event)
