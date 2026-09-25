"""Retrieval helpers: understand "yesterday"/"last week", rank memories.

All datetimes here are naive UTC. `tz_minutes` is the user's offset (IST = 330).
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


def _local_midnight(now_utc: datetime, tz_minutes: int) -> datetime:
    local = now_utc + timedelta(minutes=tz_minutes)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def parse_time_window(question: str, now_utc: datetime, tz_minutes: int = 330) -> Optional[tuple[datetime, datetime]]:
    """Return (start_utc, end_utc) if the question names a time, else None."""
    q = (question or "").lower()
    off = timedelta(minutes=tz_minutes)
    today = _local_midnight(now_utc, tz_minutes)  # local midnight, expressed in local time

    def to_utc(a, b):
        return a - off, b - off

    if "this morning" in q:
        return to_utc(today, today + timedelta(hours=12))
    if "this evening" in q or "tonight" in q:
        return to_utc(today + timedelta(hours=16), today + timedelta(days=1))
    if "last night" in q:
        return to_utc(today - timedelta(hours=6), today + timedelta(hours=6))
    if re.search(r"\btoday\b", q):
        return to_utc(today, today + timedelta(days=1))
    if re.search(r"\byesterday\b", q):
        return to_utc(today - timedelta(days=1), today)
    m = re.search(r"\b(\d{1,2}|two|three|four|five|six|seven) days ago\b", q)
    if m:
        words = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
        n = int(m.group(1)) if m.group(1).isdigit() else words[m.group(1)]
        d = today - timedelta(days=n)
        return to_utc(d, d + timedelta(days=1))
    week_start = today - timedelta(days=today.weekday())  # Monday
    if "this week" in q:
        return to_utc(week_start, today + timedelta(days=1))
    if "last week" in q:
        return to_utc(week_start - timedelta(days=7), week_start)
    month_start = today.replace(day=1)
    if "this month" in q:
        return to_utc(month_start, today + timedelta(days=1))
    if "last month" in q:
        prev = (month_start - timedelta(days=1)).replace(day=1)
        return to_utc(prev, month_start)
    return None


@dataclass
class Candidate:
    record_id: int
    score: float
    context: str
    tokens: set


def rank(candidates: list[Candidate], min_score: float, relative: float, k: int) -> list[Candidate]:
    """Keep the best memories: above the absolute floor and close to the best one."""
    ordered = sorted(candidates, key=lambda c: c.score, reverse=True)
    if not ordered or ordered[0].score < min_score:
        return []
    best = ordered[0].score
    return [c for c in ordered if c.score >= min_score and c.score >= best * relative][:k]
