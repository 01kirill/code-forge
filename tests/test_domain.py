import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from codeforge.auth.infrastructure.passwords import check_password, hash_password
from codeforge.auth.presentation.schemas import Registration
from codeforge.contest.domain import Cell, Rank, calculate_cell, phase, rank
from codeforge.contest.presentation.schemas import RoomEdit
from codeforge.education.domain import Verdict, grant, level, percent, streaks, task_xp
from codeforge.education.domain.verdicts import Case, Execution, aggregate
from codeforge.education.infrastructure.judge0 import encode, verdict
from codeforge.education.presentation.csv_export import csv_gradebook
from codeforge.education.presentation.schemas import Code
from pydantic import ValidationError

START = datetime(2026, 11, 20, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("name", "password", "valid"),
    [
        ("a" * 2, "a" * 8, False),
        ("a" * 3, "a" * 8, True),
        ("a" * 32, "Я" * 72, True),
        ("a" * 33, "Я" * 72, False),
        ("demo", "a" * 7, False),
        ("demo", "a" * 73, False),
    ],
)
def test_registration_bounds(name: str, password: str, valid: bool) -> None:
    if valid:
        assert (
            Registration(email="demo@example.com", name=name, password=password).name
            == name
        )
    else:
        with pytest.raises(ValidationError):
            Registration(email="demo@example.com", name=name, password=password)


def test_unicode_password_keeps_last_character() -> None:
    password = "я" * 72
    hashed = hash_password(password)
    assert check_password(password, hashed)
    assert not check_password(password[:-1] + "ю", hashed)


@pytest.mark.parametrize(
    ("failures", "xp"), [(0, 25), (1, 20), (2, 15), (3, 10), (10, 10)]
)
def test_task_points(failures: int, xp: int) -> None:
    assert task_xp("easy", failures) == xp


def test_progress_awards_once_and_keeps_original_local_day() -> None:
    profile: dict = {"xp": 0}
    for _ in range(2):
        grant(profile, "task", "task", 20, START, "Europe/Minsk")
    assert profile["xp"] == 20
    assert profile["days"] == ["2026-11-20"]
    assert set(profile["achievements"]) == {"first", "night"}
    grant(profile, "task", "next", 25, START + timedelta(hours=1), "Europe/Minsk")
    assert profile["achievements"]["night"] == START
    assert [level(xp) for xp in (0, 99, 100, 101)] == [1, 1, 2, 2]
    assert percent(2, 5) == 40
    assert percent(0, 0) is None


def test_streak_merges_late_and_duplicate_days() -> None:
    assert streaks(["2026-11-21", "2026-11-20", "2026-11-20", "2026-11-24"]) == (1, 2)
    assert streaks(["2026-11-22", "2026-11-20", "2026-11-21"]) == (3, 3)


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (3, Verdict.AC),
        (4, Verdict.WA),
        (5, Verdict.TLE),
        (6, Verdict.CE),
        (7, Verdict.RE),
        (11, Verdict.RE),
        (13, Verdict.TECHNICAL),
    ],
)
def test_judge_uses_status_not_stdout(status: int, outcome: Verdict) -> None:
    assert verdict({"status": {"id": status}, "stdout": encode("MLE")}) == outcome
    assert (
        verdict({"status": {"id": 7}, "limit_reason": "cgroup_oom_kill"}) == Verdict.MLE
    )


def test_hidden_failure_redacts_test_and_program_output() -> None:
    cases = [
        Case("1", "2", True),
        Case("private", "expected", False),
        Case("3", "4", True),
    ]
    result = aggregate(
        cases,
        [
            Execution(Verdict.AC, stdout="2"),
            Execution(Verdict.WA, stdout="private", diagnostic="expected"),
            Execution(Verdict.TLE, stdout="4"),
        ],
    )
    assert result["verdict"] == "WA" and result["first_failed"] == 2
    hidden = next(detail for detail in result["details"] if detail["number"] == 2)
    assert hidden == {"number": 2, "verdict": Verdict.WA, "public": False}


def test_room_time_and_penalty() -> None:
    end = START + timedelta(minutes=5)
    assert phase(START, end, START - timedelta(microseconds=1)) == "countdown"
    assert phase(START, end, START) == "running"
    assert phase(START, end, end) == "finished"
    accepted = START + timedelta(minutes=12)
    attempts = [
        (accepted, "AC"),
        (START + timedelta(minutes=14), "WA"),
        (START + timedelta(minutes=2), "WA"),
        (START + timedelta(minutes=5), "CE"),
    ]
    assert calculate_cell(START, attempts) == Cell(1, accepted, 32)
    assert calculate_cell(START, attempts[1:]).penalty == 0


def test_ties_share_places_and_prizes() -> None:
    solved = {"A": Cell(0, START, 0)}
    rows = rank(
        [Rank("2", "Beta", solved), Rank("1", "Alpha", solved), Rank("3", "C", {})]
    )
    assert [(row.id, row.place) for row in rows] == [("1", 1), ("2", 1), ("3", 3)]


@pytest.mark.parametrize("minutes", [5, 600])
def test_contest_duration_ends(minutes: int) -> None:
    assert RoomEdit(title="Contest", duration=minutes).duration == minutes
    with pytest.raises(ValidationError):
        RoomEdit(title="Contest", duration=4 if minutes == 5 else 601)


def test_submission_limit_counts_encoded_bytes() -> None:
    assert Code(language="python", code="я" * 32768)
    with pytest.raises(ValidationError):
        Code(language="python", code="я" * 32769)


def test_gradebook_csv_preserves_cyrillic_commas_and_quotes() -> None:
    title = 'Урок, "Код"'
    csv_data = csv_gradebook(
        {
            "columns": [{"title": title}, {"title": "=2+2"}],
            "rows": [
                {
                    "name": "Аня",
                    "percent": 50,
                    "cells": [
                        {"status": "completed", "xp": 10, "task_xp": 25},
                        {"status": "unstarted", "xp": 0, "task_xp": 0},
                    ],
                }
            ],
        }
    )
    header, row = list(csv.reader(io.StringIO(csv_data.lstrip("\ufeff"))))
    assert header == ["Студент", title, "'=2+2", "Итог, %"]
    assert row[0] == "Аня" and row[-1] == "50"
