from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

import asyncpg
from asyncpg.pool import PoolConnectionProxy

from codeforge.auth.application.ports import AccountTransaction, DuplicateAccount
from codeforge.auth.domain import Account, RefreshSession
from codeforge.common.broker import enqueue
from codeforge.common.contracts import Document, Role


def account(row: asyncpg.Record) -> Account:
    return Account(
        row["id"],
        row["email"],
        row["name"],
        row["password_hash"],
        row["role"],
        row["timezone"],
        row["active"],
        row["version"],
        row["sessions_after"],
    )


class PostgresAccounts:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AccountTransaction]:
        try:
            async with self.pool.acquire() as conn, conn.transaction():
                yield PostgresAccountTransaction(conn)
        except asyncpg.UniqueViolationError as exc:
            field = "email" if exc.constraint_name == "users_email_key" else "name"
            raise DuplicateAccount(field) from exc

    async def get(self, id_: UUID) -> Account | None:
        row = await self.pool.fetchrow("SELECT * FROM users WHERE id=$1", id_)
        return account(row) if row is not None else None

    async def by_email(self, email: str) -> Account | None:
        row = await self.pool.fetchrow("SELECT * FROM users WHERE email=$1", email)
        return account(row) if row is not None else None

    async def search(self, query: str) -> list[Account]:
        rows = await self.pool.fetch(
            "SELECT * FROM users WHERE strpos(lower(name::text),lower($1))>0 "
            "OR strpos(lower(email::text),lower($1))>0 OR $1='' ORDER BY name LIMIT 50",
            query,
        )
        return [account(row) for row in rows]

    async def has_administrator(self) -> bool:
        return bool(
            await self.pool.fetchval(
                "SELECT EXISTS(SELECT 1 FROM users WHERE role='admin')"
            )
        )


class PostgresAccountTransaction:
    def __init__(self, connection: PoolConnectionProxy) -> None:
        self.conn = connection

    async def create(
        self, id_: UUID, email: str, name: str, password_hash: str, role: Role
    ) -> Account:
        row = await self.conn.fetchrow(
            "INSERT INTO users(id,email,name,password_hash,role) "
            "VALUES($1,$2,$3,$4,$5) RETURNING *",
            id_,
            email,
            name,
            password_hash,
            role,
        )
        assert row is not None
        return account(row)

    async def lock_account(self, id_: UUID) -> Account | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM users WHERE id=$1 FOR UPDATE", id_
        )
        return account(row) if row is not None else None

    async def refresh_session(self, digest: str) -> RefreshSession | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM refresh_tokens WHERE digest=$1", digest
        )
        if row is None:
            return None
        return RefreshSession(
            digest,
            row["sid"],
            row["user_id"],
            row["expires_at"],
            row["revoked_at"],
        )

    async def add_session(self, session: RefreshSession, agent: str) -> None:
        await self.conn.execute(
            "INSERT INTO refresh_tokens(digest,sid,user_id,agent,expires_at) "
            "VALUES($1,$2,$3,$4,$5)",
            session.digest,
            session.sid,
            session.user_id,
            agent,
            session.expires_at,
        )

    async def revoke_refresh(self, digest: str, at: datetime) -> None:
        await self.conn.execute(
            "UPDATE refresh_tokens SET revoked_at=$2 WHERE digest=$1", digest, at
        )

    async def revoke_sessions(self, id_: UUID, sid: UUID | None = None) -> None:
        await self.conn.execute(
            "UPDATE refresh_tokens SET revoked_at=now() "
            "WHERE user_id=$1 AND ($2::uuid IS NULL OR sid=$2) AND revoked_at IS NULL",
            id_,
            sid,
        )

    async def invalidate_sessions(self, id_: UUID) -> Account:
        row = await self.conn.fetchrow(
            "UPDATE users SET version=version+1,"
            "sessions_after=version+1,updated_at=now() "
            "WHERE id=$1 RETURNING *",
            id_,
        )
        assert row is not None
        return account(row)

    async def edit_profile(self, id_: UUID, name: str, timezone: str) -> Account:
        row = await self.conn.fetchrow(
            "UPDATE users SET name=$2,timezone=$3,"
            "version=version+1,updated_at=now() WHERE id=$1 RETURNING *",
            id_,
            name,
            timezone,
        )
        assert row is not None
        return account(row)

    async def edit_access(
        self, id_: UUID, role: Role | None, active: bool | None
    ) -> Account:
        row = await self.conn.fetchrow(
            "UPDATE users SET role=COALESCE($2,role),active=COALESCE($3,active),"
            "version=version+1,updated_at=now() WHERE id=$1 RETURNING *",
            id_,
            role,
            active,
        )
        assert row is not None
        return account(row)

    async def publish_later(self, event: str, identity: Document) -> None:
        await enqueue(self.conn, event, identity)
