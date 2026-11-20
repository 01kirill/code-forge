import asyncio
import secrets
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from codeforge.common.contracts import (
    Document,
    LiveEvents,
    Problem,
    SubmissionLimiter,
    User,
)
from codeforge.contest.application.ports import (
    CodeSubmission,
    ContestData,
    ContestRepository,
    RoomDraft,
    StandingsCache,
    TaskBank,
)
from codeforge.contest.domain import Rank, calculate_cell, phase, rank


def owner_draft(row: Document, user: User) -> None:
    if str(row["owner_id"]) != user.id:
        raise Problem(403, "not_owner", "Действие доступно владельцу комнаты")
    if row["start_at"] is not None:
        raise Problem(409, "contest_started", "Комната уже запущена")


def overview(row: Document, server_time: datetime, user: User) -> Document:
    result = {
        k: row[k]
        for k in ("title", "description", "duration", "start_at", "end_at", "version")
    }
    return (
        result
        | {
            "id": str(row["id"]),
            "owner_id": str(row["owner_id"]),
            "state": phase(row["start_at"], row["end_at"], server_time),
            "server_time": server_time,
            "final": row["finished_at"] is not None,
        }
        | ({"invite": row["invite"]} if str(row["owner_id"]) == user.id else {})
    )


async def require_room(data: ContestData, id_: UUID, *, lock: bool = False) -> Document:
    row = await data.room(id_, lock=lock)
    if row is None:
        raise Problem(404, "room_missing", "Комната не найдена")
    return row


async def require_participant(data: ContestData, contest: UUID, user: UUID) -> None:
    if not await data.contains_participant(contest, user):
        raise Problem(403, "not_participant", "Вступите в комнату по приглашению")


async def scoreboard(data: ContestData, id_: UUID) -> list[Document]:
    members = {
        user_id: Rank(str(user_id), name, {})
        for user_id, name in await data.members(id_)
    }
    for user_id, label, cell in await data.cells(id_):
        members[user_id].cells[label] = cell
    return [
        {
            "id": row.id,
            "name": row.name,
            "solved": row.solved,
            "penalty": row.penalty,
            "place": row.place,
            "cells": {
                key: {
                    "failures": cell.failures,
                    "accepted": cell.accepted_at is not None,
                    "accepted_at": cell.accepted_at.isoformat()
                    if cell.accepted_at
                    else None,
                    "penalty": cell.penalty,
                }
                for key, cell in row.cells.items()
            },
        }
        for row in rank(list(members.values()))
    ]


async def request_judging(
    data: ContestData,
    attempt: Document,
    problem: Document,
) -> None:
    await data.publish_later(
        "judge.request",
        {
            "id": str(attempt["id"]),
            "task_id": problem["task_id"],
            "version": problem["task_version"],
            "language": attempt["language"],
            "code": attempt["code"],
            "practice": False,
            "submitted_at": attempt["submitted_at"].isoformat(),
            "reply": "judge.result.contest",
        },
    )


class Contests:
    def __init__(
        self,
        repository: ContestRepository,
        task_bank: TaskBank,
        cache: StandingsCache,
        events: LiveEvents,
        limiter: SubmissionLimiter,
    ) -> None:
        self.repository = repository
        self.task_bank = task_bank
        self.cache = cache
        self.events = events
        self.limiter = limiter

    async def sync_user(self, key: str, data: Document) -> None:
        user_id = UUID(data["id"])
        async with self.repository.transaction() as tx:
            await tx.sync_user(user_id, data["name"], data["version"])
        # Names are live in active rooms. Final scores keep their approved values.
        async with self.repository.read() as reader:
            ids = await reader.active_rooms_for(user_id)
        for id_ in ids:
            async with self.repository.transaction() as tx:
                await require_room(tx, id_, lock=True)
                revision = await tx.bump(id_)
                rows = await scoreboard(tx, id_)
            await self.announce(id_, revision, rows)

    async def create(self, data: RoomDraft, user: User) -> Document:
        id_ = uuid4()
        async with self.repository.transaction() as tx:
            await tx.known_user(user)
            row = await tx.create(id_, UUID(user.id), data, secrets.token_urlsafe(16))
            await tx.add_participant(id_, UUID(user.id))
            return overview(row, row["created_at"], user)

    async def list_rooms(self, user: User) -> list[Document]:
        async with self.repository.read() as reader:
            rows = await reader.rooms_for(UUID(user.id))
        return [overview(row, row["server_time"], user) for row in rows]

    async def check_membership(self, id_: UUID, user: User) -> None:
        async with self.repository.read() as reader:
            await require_participant(reader, id_, UUID(user.id))

    async def get(self, id_: UUID, user: User) -> Document:
        async with self.repository.read() as reader:
            row = await require_room(reader, id_)
            await require_participant(reader, id_, UUID(user.id))
            at = await reader.clock()
            members = await reader.members(id_)
            metadata = await reader.problem_metadata(id_)
        return overview(row, at, user) | {
            "participants": [
                {"id": str(member), "name": name} for member, name in members
            ],
            "problems": metadata,
        }

    async def edit(self, id_: UUID, data: RoomDraft, user: User) -> Document:
        async with self.repository.transaction() as tx:
            owner_draft(await require_room(tx, id_, lock=True), user)
            await tx.edit(id_, data)
        await self.events.send(f"contest:{id_}", "room.updated")
        return await self.get(id_, user)

    async def rotate_invite(self, id_: UUID, user: User) -> Document:
        token = secrets.token_urlsafe(16)
        async with self.repository.transaction() as tx:
            owner_draft(await require_room(tx, id_, lock=True), user)
            await tx.set_invite(id_, token)
        return {"invite": token}

    async def join(self, token: str, user: User) -> Document:
        async with self.repository.transaction() as tx:
            row = await tx.by_invite(token)
            if row is None:
                raise Problem(404, "invalid_invite", "Приглашение недействительно")
            id_ = row["id"]
            at = await tx.clock()
            if phase(row["start_at"], row["end_at"], at) == "finished":
                raise Problem(409, "contest_finished", "Соревнование завершено")
            await tx.known_user(user)
            if not await tx.add_participant(id_, UUID(user.id)):
                return {"id": str(id_)}
            revision = await tx.bump(id_)
            rows = await scoreboard(tx, id_)
        await self.announce(id_, revision, rows)
        await self.events.send(f"contest:{id_}", "room.updated")
        return {"id": str(id_)}

    async def replace_problems(self, id_: UUID, ids: list[str], user: User) -> Document:
        async with self.repository.read() as reader:
            owner_draft(await require_room(reader, id_), user)

        async def fetch(task_id: str) -> Document:
            if len(task_id) != 32 or any(c not in "0123456789abcdef" for c in task_id):
                raise Problem(422, "task_missing", "Проверьте идентификатор задачи")
            return await self.task_bank.snapshot(task_id)

        snapshots = await asyncio.gather(*(fetch(task_id) for task_id in ids))
        async with self.repository.transaction() as tx:
            owner_draft(await require_room(tx, id_, lock=True), user)
            await tx.replace_problems(
                id_,
                [
                    {
                        "label": chr(ord("A") + index),
                        "task_id": doc["task_id"],
                        "version": doc["version"],
                        "snapshot": doc,
                    }
                    for index, doc in enumerate(snapshots)
                ],
            )
        await self.events.send(f"contest:{id_}", "room.updated")
        return await self.get(id_, user)

    async def start(self, id_: UUID, user: User) -> Document:
        async with self.repository.transaction() as tx:
            row = await require_room(tx, id_, lock=True)
            if str(row["owner_id"]) != user.id:
                raise Problem(403, "not_owner", "Запустить может только владелец")
            at = await tx.clock()
            if row["start_at"] is not None:
                return overview(row, at, user)
            if not await tx.has_problems(id_):
                raise Problem(409, "empty_problems", "Добавьте хотя бы одну задачу")
            start = at + timedelta(seconds=10)
            end = start + timedelta(minutes=row["duration"])
            started = await tx.start(id_, start, end)
        await self.events.send(
            f"contest:{id_}", "countdown", start_at=start, server_time=at
        )
        return overview(started, at, user)

    async def problems(self, id_: UUID, user: User) -> list[Document]:
        async with self.repository.read() as reader:
            row = await require_room(reader, id_)
            await require_participant(reader, id_, UUID(user.id))
            at = await reader.clock()
            if phase(row["start_at"], row["end_at"], at) in ("draft", "countdown"):
                raise Problem(403, "not_started", "Условия откроются после старта")
            return await reader.problem_snapshots(id_)

    async def submit(
        self, id_: UUID, label: str, data: CodeSubmission, user: User
    ) -> Document:
        async with self.repository.transaction() as tx:
            row = await require_room(tx, id_, lock=True)
            user_id = UUID(user.id)
            await require_participant(tx, id_, user_id)
            problem = await tx.problem(id_, label)
            if problem is None:
                raise Problem(404, "task_missing", "Задача не найдена")
            if data.language not in problem["snapshot"]["templates"]:
                raise Problem(422, "language", "Этот язык не поддерживается задачей")
            at = await tx.clock()
            if phase(row["start_at"], row["end_at"], at) != "running":
                raise Problem(409, "contest_closed", "Приём решений закрыт")
            await self.limiter.check(user)
            attempt = await tx.create_attempt(
                uuid4(),
                id_,
                user_id,
                label,
                data,
                at,
                at + timedelta(seconds=45),
            )
            await request_judging(tx, attempt, problem)
        return self.public_attempt(attempt)

    @staticmethod
    def public_attempt(row: Document) -> Document:
        fields = ("id", "label", "language", "code", "submitted_at", "result")
        return {key: row[key] for key in fields} | {
            "state": "done" if row["result"] is not None else "queued",
        }

    async def submissions(
        self,
        id_: UUID,
        user: User,
        offset: int,
        attempt_id: UUID | None = None,
    ) -> list[Document]:
        user_id = UUID(user.id)
        async with self.repository.read() as reader:
            await require_participant(reader, id_, user_id)
            rows = await reader.attempts(id_, user_id, offset, attempt_id)
        return [self.public_attempt(row) for row in rows]

    async def standings(self, id_: UUID, user: User) -> Document:
        async with self.repository.transaction(snapshot=True) as tx:
            row = await require_room(tx, id_)
            await require_participant(tx, id_, UUID(user.id))
            pending = await tx.pending(id_)
            if row["finished_at"] is not None:
                return {
                    "rows": row["final_rows"],
                    "version": row["version"],
                    "pending": 0,
                    "final": True,
                }
            cached = await self.cache.get(id_)
            hit = cached.get("version") == row["version"]
            rows = cached["rows"] if hit else await scoreboard(tx, id_)
        if not hit:
            await self.cache.save(id_, row["version"], rows)
        return {
            "rows": rows,
            "version": row["version"],
            "pending": pending,
            "final": False,
        }

    async def announce(self, id_: UUID, revision: int, rows: list[Document]) -> None:
        await self.cache.save(id_, revision, rows)
        await self.events.send(
            f"contest:{id_}", "standings", version=revision, rows=rows
        )

    async def result(self, key: str, event: Document) -> None:
        attempt_id = UUID(event["id"])
        async with self.repository.transaction() as tx:
            attempt = await tx.attempt(attempt_id)
            if attempt is None:
                return
            id_ = attempt["contest_id"]
            contest = await require_room(tx, id_, lock=True)
            if not await tx.record_result(attempt_id, event["result"]):
                return
            user_id, label = attempt["user_id"], attempt["label"]
            before = await scoreboard(tx, id_)
            history = await tx.verdicts(id_, user_id, label)
            cell = calculate_cell(contest["start_at"], history)
            await tx.save_cell(id_, user_id, label, cell)
            revision = await tx.bump(id_)
            after = await scoreboard(tx, id_)
        await self.events.send(
            f"contest:{id_}:user:{user_id}",
            "submission.result",
            id=str(attempt_id),
            result=event["result"],
        )
        await self.announce(id_, revision, after)
        old_leaders = {
            row["id"] for row in before if row["place"] == 1 and row["solved"]
        }
        new_leaders = [
            row
            for row in after
            if row["place"] == 1 and row["solved"] and row["id"] not in old_leaders
        ]
        if new_leaders:
            await self.events.send(
                f"contest:{id_}",
                "leader_changed",
                name=new_leaders[0]["name"],
                version=revision,
            )

    async def recover(self) -> None:
        async with self.repository.transaction() as tx:
            for attempt in await tx.due_attempts():
                problem = await tx.problem(attempt["contest_id"], attempt["label"])
                assert problem is not None
                await request_judging(tx, attempt, problem)
                await tx.schedule_retry(attempt["id"])

    async def tick(self) -> None:
        events: list[tuple[UUID, str, Document]] = []
        async with self.repository.transaction() as tx:
            candidates = await tx.due_rooms()
            at = await tx.clock()
            for row in candidates:
                id_ = row["id"]
                if phase(row["start_at"], row["end_at"], at) == "running":
                    await tx.set_state(id_, "running")
                    events.append((id_, "started", {}))
                    continue
                pending = await tx.pending(id_)
                if pending:
                    await tx.set_state(id_, "finished")
                    events.append(
                        (id_, "finished", {"final": False, "pending": pending})
                    )
                    continue
                rows = await scoreboard(tx, id_)
                await tx.finish(id_, at, rows)
                await tx.publish_later(
                    "contest.finished",
                    {
                        "id": str(id_),
                        "finished_at": at.isoformat(),
                        "rows": [
                            {key: row[key] for key in ("id", "name", "place", "solved")}
                            for row in rows
                        ],
                    },
                )
                events.append((id_, "finished", {"final": True, "pending": 0}))
        for id_, event, payload in events:
            await self.events.send(f"contest:{id_}", event, **payload)
