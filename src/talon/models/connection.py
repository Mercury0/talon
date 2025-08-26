"""Connection model for Falcon API credentials."""

from dataclasses import dataclass, field
from datetime import datetime

from ..utils.time_helpers import now_utc


@dataclass
class Connection:
    """Represents a CrowdStrike Falcon API connection."""
    id: str
    client_id: str
    client_secret: str
    base_url: str
    created_at: datetime = field(default_factory=now_utc)
