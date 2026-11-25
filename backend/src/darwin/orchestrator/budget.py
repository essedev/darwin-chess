"""The daily budget, spent in hourly quotas.

By hour h of the UTC day (0-23) the agent may have spent (h + 1) / 24 of the daily budget.
A session starts only if the spend so far plus one session's ceiling fits the quota, so
the money lasts the whole day instead of burning out in the morning.
"""

from datetime import UTC, datetime, timedelta


def day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def allowance(now: datetime, daily_usd: float) -> float:
    hour = now.astimezone(UTC).hour
    return daily_usd * (hour + 1) / 24


def wait_before_session(
    now: datetime, spent_today: float, daily_usd: float, session_usd: float
) -> timedelta:
    """Zero when a session may start now, otherwise how long until the quota allows it."""
    needed = spent_today + session_usd
    if needed <= allowance(now, daily_usd):
        return timedelta(0)
    start = day_start(now)
    if needed > daily_usd:  # today's budget is gone: wait for tomorrow
        return start + timedelta(days=1) - now
    hours = max(0, int(needed / daily_usd * 24 - 1e-9))  # first hour whose quota covers it
    return max(timedelta(0), start + timedelta(hours=hours) - now)
