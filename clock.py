"""Canonical India-local clock and database timestamp helpers."""

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'


def now():
    return datetime.now(IST)


def today():
    return now().date()


def timestamp(value=None):
    return (value or now()).astimezone(IST).strftime(TIMESTAMP_FORMAT)
