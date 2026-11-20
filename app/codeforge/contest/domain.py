from dataclasses import dataclass
from datetime import datetime
from typing import Literal

type State = Literal["draft", "countdown", "running", "finished"]
PENALIZED = {"WA", "TLE", "MLE", "RE"}


@dataclass(frozen=True)
class Cell:
    failures: int
    accepted_at: datetime | None
    penalty: int


def phase(start: datetime | None, end: datetime | None, now: datetime) -> State:
    if start is None or end is None:
        return "draft"
    if now < start:
        return "countdown"
    if now < end:
        return "running"
    return "finished"


def calculate_cell(start: datetime, attempts: list[tuple[datetime, str]]) -> Cell:
    failures = 0
    for submitted_at, verdict in sorted(attempts, key=lambda attempt: attempt[0]):
        if verdict == "AC":
            elapsed = int((submitted_at - start).total_seconds() // 60)
            return Cell(failures, submitted_at, elapsed + 20 * failures)
        failures += int(verdict in PENALIZED)
    return Cell(failures, None, 0)


@dataclass
class Rank:
    id: str
    name: str
    cells: dict[str, Cell]
    solved: int = 0
    penalty: int = 0
    place: int = 0


def rank(participants: list[Rank]) -> list[Rank]:
    for row in participants:
        row.solved = sum(cell.accepted_at is not None for cell in row.cells.values())
        row.penalty = sum(cell.penalty for cell in row.cells.values())
    ordered = sorted(
        participants,
        key=lambda row: (-row.solved, row.penalty, row.name.casefold(), row.id),
    )
    previous: tuple[int, int] | None = None
    place = 0
    for index, row in enumerate(ordered, 1):
        score = row.solved, row.penalty
        if previous != score:
            place = index
        row.place = place
        previous = score
    return ordered
