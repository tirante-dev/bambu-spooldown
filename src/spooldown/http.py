"""Minimal JSON-over-HTTP helpers on the standard library.

The service makes three simple calls; a client library is not worth the
dependency.
"""

import json
import ssl
import urllib.request
from typing import Any

TIMEOUT_SECONDS = 30

# Bambu's WAF returns 403 to Python-urllib/* user agents; every other caller
# tolerates this one, so it is applied everywhere.
USER_AGENT = "bambu_network_agent/01.09.05.01"


def request_json(
    url: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    cafile: str | None = None,
) -> Any:
    """Performs one JSON request and decodes the JSON response.

    Raises urllib.error.HTTPError on non-2xx responses. `cafile` pins a CA
    bundle (the in-cluster apiserver CA) instead of the system store.
    """
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    context = ssl.create_default_context(cafile=cafile) if cafile else None
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=context) as resp:
        return json.load(resp)
