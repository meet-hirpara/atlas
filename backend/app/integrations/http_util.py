from typing import Any, Dict, Optional

import httpx


def api_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 20.0,
) -> Any:
    with httpx.Client(timeout=timeout) as client:
        resp = client.request(method, url, headers=headers, json=json, data=data, params=params)
        resp.raise_for_status()
        if resp.content:
            try:
                return resp.json()
            except Exception:
                return resp.text
        return {}
