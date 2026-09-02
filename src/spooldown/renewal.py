"""Automatic Bambu cloud token renewal via the email-code login.

Bambu's refresh endpoint is dead (401 for everyone), so renewal replays the
login: request a code, read it from a receive-only mailbox that Gmail
forwards Bambu's verification emails into (a Mailpit API), and complete the
login. The code and tokens must never be logged.
"""

import logging
import re
import time
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from spooldown.cloud import TokenManager
from spooldown.http import request_json

log = logging.getLogger(__name__)

SEND_CODE_URL = "https://api.bambulab.com/v1/user-service/user/sendemail/code"
LOGIN_URL = "https://api.bambulab.com/v1/user-service/user/login"

POLL_INTERVAL_SECONDS = 15
POLL_DEADLINE_SECONDS = 300
MIN_ATTEMPT_INTERVAL_SECONDS = 20 * 3600
CODE_PATTERN = re.compile(r"\b\d{6}\b")


def extract_code(text: str) -> str | None:
    m = CODE_PATTERN.search(text)
    return m.group(0) if m else None


def pick_message(messages: list[dict[str, Any]], not_before: datetime) -> str | None:
    """Returns the ID of the newest message created after the request time.

    Old codes linger in the mailbox; the timestamp gate is what prevents
    replaying yesterday's code.
    """
    for msg in messages:
        try:
            created = datetime.fromisoformat(str(msg.get("Created", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if created > not_before:
            return str(msg["ID"])
    return None


class Renewer:
    """Runs the full code-login renewal and adopts the new pair."""

    def __init__(
        self,
        mailbox_url: str,
        account_email: str,
        tokens: TokenManager,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._mailbox = mailbox_url.rstrip("/")
        self._email = account_email
        self._tokens = tokens
        self._sleep = sleep
        self._last_attempt = 0.0

    def renew(self) -> bool:
        """Blocking, takes minutes; call from a background thread only.

        Each attempt emails the user a code, so failed attempts back off to
        one per MIN_ATTEMPT_INTERVAL_SECONDS rather than one per loop pass.
        """
        now = time.monotonic()
        if now - self._last_attempt < MIN_ATTEMPT_INTERVAL_SECONDS:
            return False
        self._last_attempt = now
        not_before = datetime.now(UTC)
        try:
            request_json(
                SEND_CODE_URL, method="POST", body={"email": self._email, "type": "codeLogin"}
            )
        except (OSError, ValueError) as e:
            log.warning("token renewal: code request failed: %s", e)
            return False
        log.info("token renewal: code requested, polling mailbox")
        message_id = self._await_message(not_before)
        if message_id is None:
            log.warning("token renewal: no verification email within %ds", POLL_DEADLINE_SECONDS)
            return False
        code = self._fetch_code(message_id)
        if code is None:
            log.warning("token renewal: no code found in message")
            return False
        if not self._login(code):
            return False
        self._delete_message(message_id)
        log.info("token renewal: succeeded, new pair adopted")
        return True

    def _login(self, code: str) -> bool:
        try:
            out = request_json(
                LOGIN_URL,
                method="POST",
                body={"account": self._email, "code": code, "loginType": "verifyCode"},
            )
        except (OSError, ValueError) as e:
            log.warning("token renewal: login failed: %s", e)
            return False
        access = (out or {}).get("accessToken")
        refresh = (out or {}).get("refreshToken")
        if not access:
            log.warning("token renewal: login returned no accessToken")
            return False
        self._tokens.adopt(access, refresh or "")
        return True

    def _await_message(self, not_before: datetime) -> str | None:
        query = urllib.parse.urlencode({"query": "from:bambulab", "limit": 5})
        deadline = time.monotonic() + POLL_DEADLINE_SECONDS
        while time.monotonic() < deadline:
            try:
                out = request_json(f"{self._mailbox}/api/v1/search?{query}")
                found = pick_message((out or {}).get("messages") or [], not_before)
                if found is not None:
                    return found
            except OSError as e:
                log.warning("token renewal: mailbox poll failed: %s", e)
            self._sleep(POLL_INTERVAL_SECONDS)
        return None

    def _fetch_code(self, message_id: str) -> str | None:
        try:
            out = request_json(f"{self._mailbox}/api/v1/message/{message_id}")
        except OSError as e:
            log.warning("token renewal: message fetch failed: %s", e)
            return None
        return extract_code(str(out.get("Text", "")))

    def _delete_message(self, message_id: str) -> None:
        """Best-effort cleanup of the consumed code email.

        Mailpit answers this DELETE with a plain-text body, and a failure
        here must not fail a renewal that already adopted the new pair.
        """
        try:
            request_json(
                f"{self._mailbox}/api/v1/messages", method="DELETE", body={"IDs": [message_id]}
            )
        except (OSError, ValueError) as e:
            log.debug("token renewal: message cleanup failed: %s", e)
