"""Environment-driven configuration.

All settings come from the environment so the container needs no config file.
The printer access code is a secret; everything else is plain.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Runtime settings for one printer and one Spoolman instance."""

    printer_host: str
    printer_serial: str
    access_code: str
    printer_name: str
    spoolman_url: str
    cloud_token: str | None
    cloud_refresh_token: str | None
    token_secret_name: str | None
    token_state_path: str
    ledger_path: str
    partial_on_cancel: bool
    health_port: int

    @staticmethod
    def from_env(env: dict[str, str] | None = None) -> "Config":
        """Builds a Config from the process environment, failing fast on gaps."""
        e = os.environ if env is None else env
        missing = [
            k
            for k in ("PRINTER_HOST", "PRINTER_SERIAL", "ACCESS_CODE", "SPOOLMAN_URL")
            if not e.get(k)
        ]
        if missing:
            raise SystemExit(f"missing required environment: {', '.join(missing)}")
        return Config(
            printer_host=e["PRINTER_HOST"],
            printer_serial=e["PRINTER_SERIAL"],
            access_code=e["ACCESS_CODE"],
            printer_name=e.get("PRINTER_NAME", ""),
            spoolman_url=e["SPOOLMAN_URL"].rstrip("/"),
            cloud_token=e.get("BAMBU_CLOUD_TOKEN") or None,
            cloud_refresh_token=e.get("BAMBU_CLOUD_REFRESH_TOKEN") or None,
            token_secret_name=e.get("TOKEN_SECRET_NAME") or None,
            token_state_path=e.get("TOKEN_STATE_PATH", "/data/cloud-token.json"),
            ledger_path=e.get("LEDGER_PATH", "/data/ledger.json"),
            partial_on_cancel=e.get("PARTIAL_ON_CANCEL", "true").lower() != "false",
            health_port=int(e.get("HEALTH_PORT", "8080")),
        )
