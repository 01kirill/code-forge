import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from codeforge.auth.application.ports import (
    AccessSigner,
    AccountRepository,
    AccountTransaction,
    DuplicateAccount,
    Passwords,
    SessionState,
)
from codeforge.auth.domain import Account, RefreshSession, digest
from codeforge.common.contracts import Document, Problem, Role, User

REFRESH_DAYS = 30


def require_account(account: Account | None) -> Account:
    if account is None:
        raise Problem(404, "user_missing", "Пользователь не найден")
    return account


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise Problem(403, "forbidden", "Недостаточно прав")


class Accounts:
    def __init__(
        self,
        repository: AccountRepository,
        passwords: Passwords,
        state: SessionState,
        tokens: AccessSigner,
    ) -> None:
        self.repository = repository
        self.passwords = passwords
        self.state = state
        self.tokens = tokens

    async def register(
        self,
        email: str,
        name: str,
        password: str,
        role: Role = "student",
        *,
        ip: str | None = None,
    ) -> Document:
        if ip is not None and not await self.state.allow_registration(ip):
            raise Problem(
                429, "registration_limit", "Повторите регистрацию через минуту"
            )
        hashed = await self.passwords.hash(password)
        try:
            async with self.repository.transaction() as tx:
                account = await tx.create(uuid4(), email.lower(), name, hashed, role)
                data = account.identity()
                await tx.publish_later("user.registered", data)
        except DuplicateAccount as exc:
            raise Problem(
                409, f"duplicate_{exc.field}", "Имя или почта уже используются"
            ) from exc
        return data

    async def first_administrator(
        self, email: str, name: str, password: str
    ) -> Document | None:
        if await self.repository.has_administrator():
            return None
        return await self.register(email, name, password, "admin")

    async def new_session(
        self, tx: AccountTransaction, account: Account, sid: UUID, agent: str
    ) -> tuple[str, str]:
        refresh = secrets.token_urlsafe(48)
        await tx.add_session(
            RefreshSession(
                digest(refresh),
                sid,
                account.id,
                datetime.now(UTC) + timedelta(days=REFRESH_DAYS),
            ),
            agent[:256],
        )
        await self.state.publish_identity("user.updated", account.identity())
        await self.state.activate(str(sid))
        return self.tokens.issue(account.principal(sid)), refresh

    async def login(
        self, email: str, password: str, ip: str, agent: str
    ) -> tuple[str, str]:
        email = email.lower()
        if not await self.state.allow_login(ip, email):
            raise Problem(429, "login_limit", "Повторите вход через минуту")
        account = await self.repository.by_email(email)
        valid = await self.passwords.matches(
            password, account.password_hash if account else None
        )
        if account is None or not valid:
            raise Problem(401, "invalid_credentials", "Неверная почта или пароль")
        async with self.repository.transaction() as tx:
            locked = require_account(await tx.lock_account(account.id))
            if not locked.active:
                raise Problem(403, "blocked", "Аккаунт заблокирован")
            return await self.new_session(tx, locked, uuid4(), agent)

    async def rotate(self, raw: str, agent: str) -> tuple[str, str]:
        fingerprint = digest(raw)
        async with self.repository.transaction() as tx:
            original = await tx.refresh_session(fingerprint)
            if original is None:
                raise Problem(401, "session", "Войдите в аккаунт")
            user = require_account(await tx.lock_account(original.user_id))
            token = await tx.refresh_session(fingerprint)
            assert token is not None
            now = datetime.now(UTC)
            if token.expires_at <= now or not user.active:
                raise Problem(401, "session", "Войдите в аккаунт")
            if token.revoked_at is None:
                await tx.revoke_refresh(fingerprint, now)
                return await self.new_session(tx, user, token.sid, agent)
            state = await self.revoke_all(tx, user.id)
        await self.state.publish_identity("user.updated", state)
        raise Problem(401, "session_reused", "Сеансы завершены. Войдите снова")

    async def revoke_all(self, tx: AccountTransaction, user_id: UUID) -> Document:
        account = await tx.invalidate_sessions(user_id)
        await tx.revoke_sessions(user_id)
        state = account.identity()
        await tx.publish_later("user.updated", state)
        return state

    async def logout(self, user: User) -> None:
        async with self.repository.transaction() as tx:
            require_account(await tx.lock_account(UUID(user.id)))
            await tx.revoke_sessions(UUID(user.id), UUID(user.sid))
            await self.state.revoke(user.sid)

    async def me(self, user: User) -> Document:
        account = require_account(await self.repository.get(UUID(user.id)))
        return account.identity() | {"email": account.email}

    async def public_user(self, id_: UUID) -> Document:
        account = require_account(await self.repository.get(id_))
        if not account.active:
            raise Problem(404, "user_missing", "Пользователь не найден")
        return {"id": str(account.id), "name": account.name}

    async def search(self, user: User, query: str) -> list[Document]:
        require_admin(user)
        return [
            account.identity() | {"email": account.email}
            for account in await self.repository.search(query[:254])
        ]

    async def update_profile(self, user: User, name: str, timezone: str) -> Document:
        try:
            async with self.repository.transaction() as tx:
                state = (
                    await tx.edit_profile(UUID(user.id), name, timezone)
                ).identity()
                await tx.publish_later("user.updated", state)
        except DuplicateAccount as exc:
            raise Problem(409, "duplicate_name", "Имя уже используется") from exc
        await self.state.publish_identity("user.updated", state)
        return state

    async def change_access(
        self, actor: User, user_id: UUID, role: Role | None, active: bool | None
    ) -> Document:
        require_admin(actor)
        if role is None and active is None:
            raise Problem(400, "empty_change", "Укажите новое состояние или роль")
        async with self.repository.transaction() as tx:
            target = require_account(await tx.lock_account(user_id))
            if target.role == "admin" or actor.id == str(user_id):
                raise Problem(403, "forbidden", "Доступ администратора защищён")
            account = await tx.edit_access(user_id, role, active)
            if active is False:
                state = await self.revoke_all(tx, user_id)
            else:
                state = account.identity()
                await tx.publish_later("user.updated", state)
        await self.state.publish_identity("user.updated", state)
        return state
