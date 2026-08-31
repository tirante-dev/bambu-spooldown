"""Bambu cloud token lifecycle.

Access tokens expire after roughly 90 days; the login response also carries a
refresh token, and the refresh endpoint returns a fresh pair. The manager
keeps the current pair in a store (Kubernetes Secret in-cluster, JSON file
otherwise) so rotation survives restarts; the env-provided pair is only a
seed for an empty store. Token values must never be logged.
"""

import base64
import json
import logging
import os
import time
import urllib.error
from typing import Protocol

from spooldown.http import request_json

log = logging.getLogger(__name__)

REFRESH_URL = "https://api.bambulab.com/v1/user-service/user/refreshtoken"
PROACTIVE_REFRESH_AFTER_SECONDS = 30 * 24 * 3600
RENEWAL_WARNING_AFTER_SECONDS = 75 * 24 * 3600

SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"


class TokenStore(Protocol):
    def load(self) -> dict[str, str] | None: ...
    def save(self, state: dict[str, str]) -> None: ...


class FileTokenStore:
    """JSON-file store for non-Kubernetes deployments."""

    def __init__(self, path: str) -> None:
        self._path = path

    def load(self) -> dict[str, str] | None:
        try:
            with open(self._path, encoding="utf-8") as f:
                out = json.load(f)
            return out if isinstance(out, dict) else None
        except (OSError, ValueError):
            return None

    def save(self, state: dict[str, str]) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, self._path)


class K8sSecretStore:
    """Stores the pair in a Secret spooldown owns, distinct from the sealed
    seed secret so neither ArgoCD nor sealed-secrets reconciles it away."""

    def __init__(self, secret_name: str) -> None:
        self._name = secret_name
        with open(f"{SA_DIR}/namespace", encoding="utf-8") as f:
            self._namespace = f.read().strip()
        self._base = f"https://kubernetes.default.svc/api/v1/namespaces/{self._namespace}/secrets"

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        with open(f"{SA_DIR}/token", encoding="utf-8") as f:
            headers = {"Authorization": f"Bearer {f.read().strip()}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def load(self) -> dict[str, str] | None:
        try:
            secret = request_json(
                f"{self._base}/{self._name}",
                headers=self._headers(),
                cafile=f"{SA_DIR}/ca.crt",
            )
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        data = secret.get("data") or {}
        return {k: base64.b64decode(v).decode() for k, v in data.items()}

    def save(self, state: dict[str, str]) -> None:
        encoded = {k: base64.b64encode(v.encode()).decode() for k, v in state.items()}
        body = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": self._name, "namespace": self._namespace},
            "data": encoded,
        }
        try:
            request_json(
                f"{self._base}/{self._name}",
                method="PUT",
                body=body,
                headers=self._headers(),
                cafile=f"{SA_DIR}/ca.crt",
            )
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            request_json(
                self._base,
                method="POST",
                body=body,
                headers=self._headers(),
                cafile=f"{SA_DIR}/ca.crt",
            )


class TokenManager:
    """Hands out the current access token and rotates the pair on demand."""

    def __init__(
        self,
        store: TokenStore,
        seed_access: str | None,
        seed_refresh: str | None,
    ) -> None:
        self._store = store
        self._state = store.load() or {}
        if seed_access and self._state.get("seed") != seed_access:
            # A changed seed means freshly minted tokens were sealed in;
            # adopt them and date the pair from now.
            self._state = {
                "access": seed_access,
                "refresh": seed_refresh or "",
                "seed": seed_access,
                "refreshed_at": str(int(time.time())),
            }
            try:
                store.save(self._state)
            except Exception:
                log.exception("failed to persist seeded cloud token; continuing in memory")

    def access(self) -> str | None:
        return self._state.get("access") or None

    def age_seconds(self) -> float | None:
        at = self._state.get("refreshed_at")
        try:
            return time.time() - float(at) if at else None
        except (TypeError, ValueError):
            return None

    def refresh(self) -> bool:
        token = self._state.get("refresh")
        if not token:
            log.warning("no refresh token available; re-seed BAMBU_CLOUD_REFRESH_TOKEN")
            return False
        try:
            out = request_json(REFRESH_URL, method="POST", body={"refreshToken": token})
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            log.warning("cloud token refresh failed: %s", e)
            return False
        access, refresh = out.get("accessToken"), out.get("refreshToken")
        if not access:
            log.warning("cloud token refresh returned no accessToken")
            return False
        self._state = {
            "access": access,
            "refresh": refresh or token,
            "seed": self._state.get("seed", ""),
            "refreshed_at": str(int(time.time())),
        }
        try:
            self._store.save(self._state)
        except Exception:
            log.exception("failed to persist refreshed cloud token; continuing in memory")
        log.info("cloud token refreshed")
        return True

    def should_refresh_proactively(self) -> bool:
        if not self._state.get("refresh"):
            return False
        age = self.age_seconds()
        return age is None or age > PROACTIVE_REFRESH_AFTER_SECONDS

    def needs_renewal(self) -> bool:
        """True when the pair is old enough that a human should re-login.

        Bambu's refresh endpoint rejects tokens minted by the email-code
        login, so rotation cannot be assumed to work; access tokens die at
        roughly 90 days and this warns with margin.
        """
        if not self._state.get("access"):
            return False
        age = self.age_seconds()
        return age is not None and age > RENEWAL_WARNING_AFTER_SECONDS
