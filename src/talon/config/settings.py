"""Application state and configuration management."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..api.client import FalconClient
from ..models import AlertFilter, AlertStats, Connection, OutputFormat


class TalonState:
    """Main application state and configuration."""

    def __init__(self):
        self.connections: List[Connection] = []
        self.active_id: Optional[str] = None
        self.connected: bool = False
        self.poll_interval: int = 15  # seconds (default 15s)
        self.client: Optional[FalconClient] = None  # persistent client for token reuse
        self.alert_filter: AlertFilter = AlertFilter()
        self.output_format: OutputFormat = OutputFormat.CONSOLE
        self.log_file: Optional[Path] = None
        self.alert_stats: AlertStats = AlertStats()
        self.lookback_minutes: int = 10  # Default lookback in minutes

    def active(self) -> Optional[Connection]:
        """Get the currently active connection."""
        if not self.active_id:
            return None
        for c in self.connections:
            if c.id == self.active_id:
                return c
        return None

    def save_config(self):
        """Save configuration to disk."""
        config_dir = Path.home() / ".talon"
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / "config.json"

        data = {
            "connections": [
                {
                    "id": c.id,
                    "client_id": c.client_id,
                    "client_secret": c.client_secret,  # Consider encryption
                    "base_url": c.base_url,
                    "created_at": c.created_at.isoformat(),
                }
                for c in self.connections
            ],
            "active_id": self.active_id,
            "poll_interval": self.poll_interval,
        }

        with open(config_file, "w") as f:
            json.dump(data, f, indent=2)

    def load_config(self):
        """Load configuration from disk."""
        config_file = Path.home() / ".talon" / "config.json"
        if not config_file.exists():
            return

        try:
            with open(config_file, "r") as f:
                data = json.load(f)

            for conn_data in data.get("connections", []):
                conn = Connection(
                    id=conn_data["id"],
                    client_id=conn_data["client_id"],
                    client_secret=conn_data["client_secret"],
                    base_url=conn_data["base_url"],
                    created_at=datetime.fromisoformat(conn_data["created_at"]),
                )
                self.connections.append(conn)

            self.active_id = data.get("active_id")
            self.poll_interval = data.get("poll_interval", 15)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")

    def matches_filter(self, alert: dict, filter_obj: AlertFilter) -> bool:
        """Check if an alert matches the current filter criteria."""
        # Severity filtering
        if filter_obj.severity_min is not None:
            try:
                sev = int(alert.get("severity", 0))
                if sev < filter_obj.severity_min:
                    return False
            except ValueError:
                pass

        # Product filtering
        if filter_obj.product:
            prod = str(alert.get("product", "")).upper()
            if filter_obj.product.upper() not in prod:
                return False

        # Hostname filtering
        if filter_obj.hostname:
            dev = alert.get("device", {})
            host = dev.get("hostname", "") if isinstance(dev, dict) else ""
            if filter_obj.hostname.lower() not in host.lower():
                return False

        # Keyword filtering
        if filter_obj.keywords:
            text = f"{alert.get('name', '')} {alert.get('description', '')}".lower()
            if not any(kw.lower() in text for kw in filter_obj.keywords):
                return False

        return True
