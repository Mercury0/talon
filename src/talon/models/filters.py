"""Alert filtering and statistics models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

from ..utils.time_helpers import now_utc


@dataclass
class AlertFilter:
    """Configuration for filtering alerts."""
    severity_min: Optional[int] = None
    product: Optional[str] = None
    hostname: Optional[str] = None
    status: Optional[str] = None
    keywords: List[str] = field(default_factory=list)


class OutputFormat(Enum):
    """Available output formats."""
    CONSOLE = "console"
    JSON = "json"
    CSV = "csv"


@dataclass
class AlertStats:
    """Statistics tracking for alerts."""
    total_alerts: int = 0
    alerts_by_severity: dict = field(default_factory=dict)
    alerts_by_product: dict = field(default_factory=dict)
    last_reset: datetime = field(default_factory=now_utc)
    
    def add_alert(self, alert: dict):
        """Add an alert to the statistics."""
        self.total_alerts += 1
        
        # Track by severity
        sev = str(alert.get("severity", "unknown"))
        self.alerts_by_severity[sev] = self.alerts_by_severity.get(sev, 0) + 1
        
        # Track by product
        prod = str(alert.get("product", "unknown"))
        self.alerts_by_product[prod] = self.alerts_by_product.get(prod, 0) + 1
    
    def reset(self):
        """Reset all statistics."""
        self.total_alerts = 0
        self.alerts_by_severity.clear()
        self.alerts_by_product.clear()
        self.last_reset = now_utc()
