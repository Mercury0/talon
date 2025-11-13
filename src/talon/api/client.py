"""CrowdStrike Falcon API client."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

try:
    import requests  # type: ignore[import-untyped]
    from requests import RequestException as _RequestException  # type: ignore[import-untyped]
    RequestException = _RequestException
except ImportError as err:
    RequestException = Exception
    raise ImportError(
        "This tool requires the 'requests' package. Try: pip install requests"
    ) from err

class FalconClient:
    """Client for interacting with CrowdStrike Falcon API."""

    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.sess = requests.Session()
        self.sess.headers["User-Agent"] = "talon/0.1.0"

        # Token state
        self._tok: Optional[str] = None
        self._exp: float = 0.0

    def is_token_valid(self) -> bool:
        """Check if the current token is still valid."""
        # Token is valid only if non-None AND not expired
        return self._tok is not None and (time.time() < self._exp - 60)

    def token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self.is_token_valid():
            # Safe: is_token_valid() ensures _tok is not None
            return self._tok  # type: ignore[return-value]

        # Refresh the token
        url = f"{self.base_url}/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        r = self.sess.post(url, data=data, timeout=30)
        r.raise_for_status()

        js: Dict[str, Any] = r.json()
        token = js["access_token"]
        expires = int(js.get("expires_in", 1800))

        self._tok = token
        self._exp = time.time() + expires
        self.sess.headers["Authorization"] = f"Bearer {token}"

        return token

    def query_alert_ids(self, since_created_iso: str, limit: int = 5000) -> List[str]:
        """
        Return alert IDs created strictly after since_created_iso.
        Sorted by created_timestamp asc so our watermark can advance deterministically.
        """
        self.token()
        params: Dict[str, str] = {
            "filter": f"created_timestamp:>'{since_created_iso}'",
            "sort": "created_timestamp.asc",
            "limit": str(limit),
            "offset": "0",
        }

        ids: List[str] = []
        more = True

        while more:
            r = self.sess.get(
                f"{self.base_url}/alerts/queries/alerts/v1",
                params=params,
                timeout=60,
            )

            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "2")) or 2)
                continue

            r.raise_for_status()

            j: Dict[str, Any] = r.json()
            resources = j.get("resources") or []
            if isinstance(resources, list):
                ids.extend(resources)

            meta = (j.get("meta") or {}).get("pagination") or {}
            offset = int(meta.get("offset", 0))
            lim = int(meta.get("limit", len(resources)))
            total = int(meta.get("total", len(resources)))

            more = (offset + lim) < total
            if more:
                params["offset"] = str(offset + lim)

        return ids

    def fetch_alerts(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch alert entities by ID using POST /alerts/entities/alerts/v1.
        """
        if not ids:
            return []

        out: List[Dict[str, Any]] = []

        # Process in chunks of 500
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            self.token()

            r = self.sess.post(
                f"{self.base_url}/alerts/entities/alerts/v1",
                json={"ids": chunk},
                timeout=60,
            )

            # Handle rate limiting (429)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "2")) or 2)
                r = self.sess.post(
                    f"{self.base_url}/alerts/entities/alerts/v1",
                    json={"ids": chunk},
                    timeout=60,
                )

            r.raise_for_status()

            payload = r.json()
            resources = payload.get("resources") or []
            if isinstance(resources, list):
                out.extend(resources)

        return out
