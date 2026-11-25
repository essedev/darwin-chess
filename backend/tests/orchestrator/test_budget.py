from datetime import UTC, datetime, timedelta

from darwin.orchestrator.budget import allowance, wait_before_session

DAY = 2.0
SESSION = 0.25


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 25, hour, minute, tzinfo=UTC)


def test_allowance_grows_by_hourly_quotas() -> None:
    assert allowance(at(0), DAY) == DAY / 24
    assert allowance(at(11, 59), DAY) == DAY / 2
    assert allowance(at(23, 30), DAY) == DAY


def test_a_session_starts_at_once_within_the_quota() -> None:
    assert wait_before_session(at(12), 0.5, DAY, SESSION) == timedelta(0)


def test_overspending_waits_for_the_hour_whose_quota_covers_it() -> None:
    # 1.0 $ spent + 0.25 needs 1.25 $, covered from hour 14 (15/24 * 2 = 1.25)
    assert wait_before_session(at(9, 30), 1.0, DAY, SESSION) == timedelta(hours=4, minutes=30)


def test_an_exhausted_day_waits_for_midnight() -> None:
    assert wait_before_session(at(22), 1.9, DAY, SESSION) == timedelta(hours=2)
