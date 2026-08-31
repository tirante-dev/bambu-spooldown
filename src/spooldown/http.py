"""Minimal JSON-over-HTTP helpers on the standard library.

The service makes three simple calls; a client library is not worth the
dependency.
"""

import json
import urllib.request
from typing import Any

TIMEOUT_SECONDS = 30


def request_json(
    url: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """Performs one JSON request and decodes the JSON response.

    Raises urllib.error.HTTPError on non-2xx responses.
    """
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return json.load(resp)
