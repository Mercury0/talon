"""SQLite database for storing and retrieving alerts."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

AlertDict = Dict[str, Any]


class AlertsDB:
    """SQLite database for storing CrowdStrike alerts."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".talon" / "alerts.db"

        self.db_path: Path = db_path
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    short_id TEXT NOT NULL,
                    full_id TEXT NOT NULL,
                    name TEXT,
                    description TEXT,
                    severity INTEGER,
                    status TEXT,
                    product TEXT,
                    hostname TEXT,
                    created_timestamp TEXT,
                    updated_timestamp TEXT,
                    raw_data TEXT,
                    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(full_id)
                )
                """
            )

            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_short_id ON alerts(short_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON alerts(created_timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_severity ON alerts(severity)")

    def store_alert(self, alert_data: AlertDict, short_id: str, full_id: str) -> bool:
        """Store an alert in the database. Returns True if new, False if updated."""
        device = alert_data.get("device", {})
        hostname: Optional[str] = device.get("hostname") if isinstance(device, dict) else None

        with sqlite3.connect(self.db_path) as conn:
            # Check if alert already exists
            cursor = conn.execute("SELECT id FROM alerts WHERE full_id = ?", (full_id,))
            exists = cursor.fetchone() is not None

            conn.execute(
                """
                INSERT OR REPLACE INTO alerts
                (id, short_id, full_id, name, description, severity, status, product,
                 hostname, created_timestamp, updated_timestamp, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    short_id,  # Use short_id as primary key for user reference
                    short_id,
                    full_id,
                    alert_data.get("name"),
                    alert_data.get("description"),
                    alert_data.get("severity"),
                    alert_data.get("status"),
                    alert_data.get("product"),
                    hostname,
                    alert_data.get("created_timestamp"),
                    alert_data.get("updated_timestamp"),
                    json.dumps(alert_data),
                ),
            )

            return not exists

    def get_alert_by_short_id(self, short_id: str) -> Optional[AlertDict]:
        """Get alert data by short ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT raw_data, full_id FROM alerts
                WHERE short_id = ? OR id = ?
                """,
                (short_id, short_id),
            )

            row = cursor.fetchone()
            if not row:
                return None

            alert_data: AlertDict = json.loads(row[0])
            alert_data["_full_id"] = row[1]
            return alert_data

    def get_recent_alerts(self, limit: int = 20) -> List[AlertDict]:
        """Get recent alerts for selection."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT short_id, name, severity, status, hostname, created_timestamp, full_id
                FROM alerts
                ORDER BY created_timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )

            result: List[AlertDict] = []
            for row in cursor.fetchall():
                result.append(
                    {
                        "short_id": row[0],
                        "name": row[1],
                        "severity": row[2],
                        "status": row[3],
                        "hostname": row[4],
                        "created_timestamp": row[5],
                        "full_id": row[6],
                    }
                )
            return result

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM alerts")
            total: int = cursor.fetchone()[0]

            cursor = conn.execute(
                """
                SELECT severity, COUNT(*) FROM alerts
                GROUP BY severity ORDER BY severity DESC
                """
            )
            by_severity: Dict[str, int] = dict(cursor.fetchall())

            cursor = conn.execute(
                """
                SELECT product, COUNT(*) FROM alerts
                GROUP BY product ORDER BY COUNT(*) DESC
                """
            )
            by_product: Dict[str, int] = dict(cursor.fetchall())

            return {
                "total": total,
                "by_severity": by_severity,
                "by_product": by_product,
            }

    def get_daily_stats(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a specific day. If date_str is None, use today."""
        if date_str is None:
            from ..utils.time_helpers import now_utc

            date_str = now_utc().strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            # Total for the day
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM alerts
                WHERE DATE(created_timestamp) = ?
                """,
                (date_str,),
            )
            total: int = cursor.fetchone()[0]

            # By severity
            cursor = conn.execute(
                """
                SELECT severity, COUNT(*) FROM alerts
                WHERE DATE(created_timestamp) = ?
                GROUP BY severity ORDER BY severity DESC
                """,
                (date_str,),
            )
            by_severity: Dict[str, int] = dict(cursor.fetchall())

            # By product
            cursor = conn.execute(
                """
                SELECT product, COUNT(*) FROM alerts
                WHERE DATE(created_timestamp) = ?
                GROUP BY product ORDER BY COUNT(*) DESC
                """,
                (date_str,),
            )
            by_product: Dict[str, int] = dict(cursor.fetchall())

            return {
                "date": date_str,
                "total": total,
                "by_severity": by_severity,
                "by_product": by_product,
            }

    def purge_alerts(self) -> int:
        """Remove all alerts from database. Returns count of deleted alerts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM alerts")
            count: int = cursor.fetchone()[0]

            conn.execute("DELETE FROM alerts")
            return count

    def export_alerts_csv(self, output_file: Path) -> int:
        """Export alerts to CSV format. Returns count of exported alerts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT short_id, name, severity, status, product, hostname,
                       created_timestamp, updated_timestamp, description
                FROM alerts
                ORDER BY created_timestamp DESC
                """
            )

            count = 0
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "ID",
                        "Name",
                        "Severity",
                        "Status",
                        "Product",
                        "Hostname",
                        "Created",
                        "Updated",
                        "Description",
                    ]
                )

                for row in cursor:
                    writer.writerow(row)
                    count += 1

                return count

    def export_alerts_json(self, output_file: Path) -> int:
        """Export alerts to JSON format. Returns count of exported alerts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT raw_data FROM alerts
                ORDER BY created_timestamp DESC
                """
            )

            alerts: List[AlertDict] = []
            for row in cursor:
                alerts.append(json.loads(row[0]))

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(alerts, f, indent=2, ensure_ascii=False)

            return len(alerts)
