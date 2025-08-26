"""CrowdStrike Falcon API client."""

import time
from typing import List, Optional

try:
    import requests
    from requests import RequestException
except ImportError:
    raise ImportError("This tool requires the 'requests' package. Try: pip install requests")


class FalconClient:
    """Client for interacting with CrowdStrike Falcon API."""
    
    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.sess = requests.Session()
        self.sess.headers["User-Agent"] = "talon/0.1.0"
        self._tok: Optional[str] = None
        self._exp: float = 0.0

    def is_token_valid(self) -> bool:
        """Check if the current token is still valid."""
        return bool(self._tok) and (time.time() < self._exp - 60)

    def token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self.is_token_valid():
            return self._tok
        
        url = f"{self.base_url}/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        r = self.sess.post(url, data=data, timeout=30)
        r.raise_for_status()
        
        js = r.json()
        self._tok = js["access_token"]
        self._exp = time.time() + int(js.get("expires_in", 1800))
        self.sess.headers["Authorization"] = f"Bearer {self._tok}"
        
        return self._tok

    def query_alert_ids(self, since_created_iso: str, limit: int = 5000) -> List[str]:
        """
        Return alert IDs created strictly after since_created_iso.
        We sort by created_timestamp asc so our watermark can advance deterministically.
        """
        self.token()
        params = {
            "filter": f"created_timestamp:>'{since_created_iso}'",
            "sort": "created_timestamp.asc",
            "limit": str(limit),
            "offset": "0",
        }
        
        ids, more = [], True
        while more:
            r = self.sess.get(f"{self.base_url}/alerts/queries/alerts/v1", params=params, timeout=60)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "2")) or 2)
                continue
            r.raise_for_status()
            
            j = r.json()
            ids.extend(j.get("resources", []) or [])
            
            meta = (j.get("meta") or {}).get("pagination") or {}
            offset = int(meta.get("offset", 0))
            lim = int(meta.get("limit", len(ids)))
            total = int(meta.get("total", len(ids)))
            more = (offset + lim) < total
            
            if more:
                params["offset"] = str(offset + lim)
        
        return ids

    def fetch_alerts(self, ids: List[str]) -> List[dict]:
        """
        Fetch alert entities by ID using POST /alerts/entities/alerts/v1 with JSON body.
        """
        if not ids:
            return []
        
        out: List[dict] = []
        for i in range(0, len(ids), 500):
            chunk = ids[i:i+500]
            self.token()
            
            r = self.sess.post(
                f"{self.base_url}/alerts/entities/alerts/v1",
                json={"ids": chunk},
                timeout=60,
            )
            
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "2")) or 2)
                r = self.sess.post(
                    f"{self.base_url}/alerts/entities/alerts/v1",
                    json={"ids": chunk},
                    timeout=60,
                )
            
            r.raise_for_status()
            out.extend(r.json().get("resources") or [])
        
        return out
