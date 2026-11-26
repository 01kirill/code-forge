from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo


class Verdict(StrEnum):
    AC = "AC"
    WA = "WA"
    TLE = "TLE"
    MLE = "MLE"
    RE = "RE"
    CE = "CE"
    TECHNICAL = "TECHNICAL"


TASK_XP = {"easy": 25, "medium": 50, "hard": 100}
LESSON_XP = 10
PLACE_XP = {1: 100, 2: 60, 3: 30}
ACHIEVEMENTS = {
    "first": ("Первая задача", "Решить первую задачу"),
    "ten": ("Решено 10 задач", "Решить 10 разных задач"),
    "fifty": ("Решено 50 задач", "Решить 50 разных задач"),
    "streak": ("Серия 7 дней", "Учиться семь дней подряд"),
    "night": ("Ночной кодер", "Решить задачу с 03:00 до 04:00 по местному времени"),
    "first_try": ("С первой попытки", "Решить 10 разных задач без ошибок"),
    "winner": ("Победитель", "Занять первое место в соревновании"),
}


def task_xp(difficulty: str, failures: int) -> int:
    return TASK_XP[difficulty] * (100 - 20 * min(failures, 3)) // 100


def level(xp: int) -> int:
    return 1 + xp // 100


def local_time(at: datetime, timezone: str) -> datetime:
    return at.astimezone(ZoneInfo(timezone))


def streaks(days: list[str], today: date) -> tuple[int, int]:
    previous = None
    current = best = 0
    for day in sorted({date.fromisoformat(value) for value in days}):
        current = current + 1 if previous and day - previous == timedelta(days=1) else 1
        best = max(current, best)
        previous = day
    return (current if previous and previous >= today - timedelta(days=1) else 0), best


def percent(done: int, total: int) -> int | None:
    return round(100 * done / total) if total else None


def grant(
    profile: dict[str, Any],
    kind: str,
    id_: str,
    xp: int,
    at: datetime,
    timezone: str = "UTC",
    *,
    first_try: bool = False,
    winner: bool = False,
) -> None:
    collection = {"lesson": "completed", "task": "solved", "contest": "prizes"}[kind]
    awards = profile.setdefault(collection, {})
    if id_ in awards:
        return
    awards[id_] = {"xp": xp, "at": at, "first_try": first_try}
    profile["xp"] += xp
    activity = local_time(at, timezone)
    if kind != "contest":
        days = profile.setdefault("days", [])
        day = activity.date().isoformat()
        if day not in days:
            days.append(day)
    solved = profile.get("solved", {})
    _, best = streaks(profile.get("days", []), activity.date())
    earned = profile.setdefault("achievements", {})
    conditions = {
        "first": len(solved) >= 1,
        "ten": len(solved) >= 10,
        "fifty": len(solved) >= 50,
        "streak": best >= 7,
        "night": kind == "task" and activity.hour == 3,
        "first_try": sum(value["first_try"] for value in solved.values()) >= 10,
        "winner": winner,
    }
    for code, earned_now in conditions.items():
        if earned_now:
            earned.setdefault(code, at)


def changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": level(after["xp"])
        if level(after["xp"]) > level(before["xp"])
        else None,
        "xp": after["xp"],
        "new_achievements": list(
            after.get("achievements", {}).keys() - before.get("achievements", {}).keys()
        ),
    }
