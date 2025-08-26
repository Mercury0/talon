"""Time-related utility functions."""

from datetime import datetime, timezone
from typing import Optional

UTC = timezone.utc


def now_utc() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


def fmt_ts(d: datetime) -> str:
    """Format timestamp as '2025-08-24 17:21.55 UTC'."""
    return d.astimezone(UTC).strftime("%Y-%m-%d %H:%M.%S UTC")


def fql_time(d: datetime) -> str:
    """Format datetime for Falcon Query Language."""
    return d.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_utc(s: str) -> datetime:
    """Parse ISO UTC timestamp string."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def pick_created_iso(alert: dict) -> Optional[str]:
    """Prefer created_timestamp, fallback to timestamp, then updated_timestamp."""
    return alert.get("created_timestamp") or alert.get("timestamp") or alert.get("updated_timestamp")
