"""
Attendance bookkeeping: recording check-ins/outs and summarising them.
"""

from __future__ import annotations

import datetime
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, QuerySet

from users.models import Present, Time

WORKING_DAYS_PER_WEEK = 5


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


@transaction.atomic
def mark_in(usernames: Iterable[str], when: datetime.datetime | None = None) -> list[str]:
    """
    Mark each user present for the day and log a check-in.

    Every other student without a record for the day gets an "absent" row, so
    daily reports list them. Returns the usernames that were marked present.
    """
    when = when or datetime.datetime.now()
    day = when.date()
    users = list(User.objects.filter(username__in=set(usernames)))
    for user in users:
        if not Present.objects.filter(user=user, date=day).update(present=True):
            Present.objects.create(user=user, date=day, present=True)
        Time.objects.create(user=user, date=day, time=when, out=False)

    already_recorded = Present.objects.filter(date=day).values("user_id")
    Present.objects.bulk_create(
        Present(user=user, date=day, present=False) for user in students().exclude(id__in=already_recorded)
    )
    return sorted(u.username for u in users)


@transaction.atomic
def mark_out(usernames: Iterable[str], when: datetime.datetime | None = None) -> list[str]:
    """Log a check-out for each user. Returns usernames marked."""
    when = when or datetime.datetime.now()
    users = list(User.objects.filter(username__in=set(usernames)))
    for user in users:
        Time.objects.create(user=user, date=when.date(), time=when, out=True)
    return sorted(u.username for u in users)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------


def format_hours(hours: float) -> str:
    whole = int(hours)
    minutes = math.ceil((hours - whole) * 60)
    if minutes == 60:
        whole, minutes = whole + 1, 0
    return f"{whole} hrs {minutes} mins"


def _hours_between(start: datetime.datetime, end: datetime.datetime) -> float:
    return (end - start).total_seconds() / 3600


def break_hours(events: list[Time]) -> float:
    """
    Total time spent out between check-ins on one day.

    ``events`` must be sorted by time. The sequence is only meaningful when it
    strictly alternates in, out, in, out, ...; anything else yields 0.
    """
    if not events or len(events) % 2 or events[0].out:
        return 0.0
    if any(event.out != bool(i % 2) for i, event in enumerate(events)):
        return 0.0
    # Pairs of (check-out, following check-in).
    return sum(_hours_between(events[i].time, events[i + 1].time) for i in range(1, len(events) - 1, 2))


@dataclass
class DailyAttendance:
    """One row of an attendance report."""

    user: User
    date: datetime.date
    present: bool
    time_in: datetime.datetime | None
    time_out: datetime.datetime | None
    hours_value: float
    break_hours_value: float

    @property
    def hours(self) -> str:
        return format_hours(self.hours_value)

    @property
    def break_hours(self) -> str:
        return format_hours(self.break_hours_value)


def daily_attendance(present_qs: QuerySet[Present], time_qs: QuerySet[Time]) -> list[DailyAttendance]:
    """Combine Present rows with their Time events into per-user, per-day rows."""
    events: dict[tuple[int, datetime.date], list[Time]] = defaultdict(list)
    for event in time_qs.exclude(time=None).order_by("time"):
        events[(event.user_id, event.date)].append(event)

    rows = []
    for record in present_qs.select_related("user"):
        day = events.get((record.user_id, record.date), [])
        ins = [e.time for e in day if not e.out]
        outs = [e.time for e in day if e.out]
        time_in = ins[0] if ins else None
        time_out = outs[-1] if outs else None
        hours = _hours_between(time_in, time_out) if time_in and time_out else 0.0
        rows.append(
            DailyAttendance(
                user=record.user,
                date=record.date,
                present=record.present,
                time_in=time_in,
                time_out=time_out,
                hours_value=hours,
                break_hours_value=break_hours(day),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def students() -> QuerySet[User]:
    """Every non-staff account, i.e. everyone who is not an administrator."""
    return User.objects.filter(is_staff=False, is_superuser=False)


def present_count(day: datetime.date) -> int:
    return Present.objects.filter(date=day, present=True).count()


def monday_of(day: datetime.date) -> datetime.date:
    return day - datetime.timedelta(days=day.weekday())


def weekly_present_counts(monday: datetime.date) -> list[tuple[datetime.date, int]]:
    """Number of students present on each working day of the week starting ``monday``."""
    days = [monday + datetime.timedelta(days=i) for i in range(WORKING_DAYS_PER_WEEK)]
    counts = dict(
        Present.objects.filter(date__in=days, present=True)
        .values_list("date")
        .annotate(n=Count("id"))
        .values_list("date", "n")
    )
    return [(day, counts.get(day, 0)) for day in days]
