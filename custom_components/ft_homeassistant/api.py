"""Minimal client for the 42 Intra API (no Home Assistant imports)."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import aiohttp

API_BASE = "https://api.intra.42.fr"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
# Renew the access token this many seconds before it expires.
TOKEN_MARGIN = 60


class FortyTwoError(Exception):
    """Generic API error."""


class FortyTwoConnectionError(FortyTwoError):
    """The API could not be reached."""


class FortyTwoAuthError(FortyTwoError):
    """The application UID or secret is invalid or expired."""


class FortyTwoRateLimitError(FortyTwoError):
    """Too many requests (2 per second, 1200 per hour per application)."""


class FortyTwoNotFoundError(FortyTwoError):
    """The requested resource (for example a login) does not exist."""


def parse_duration(value: str) -> timedelta:
    """Parse a logtime string such as ``"04:40:36.89249"``."""
    hours, minutes, seconds = value.split(":")
    return timedelta(hours=int(hours), minutes=int(minutes), seconds=float(seconds))


class FortyTwoApiClient:
    """Access the 42 API with the client credentials flow."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
        base_url: str = API_BASE,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url
        self._token: str | None = None
        self._token_expires = 0.0
        self.secret_valid_until: datetime | None = None

    async def async_authenticate(self) -> None:
        """Get a new access token, raising FortyTwoAuthError on bad credentials."""
        try:
            async with self._session.post(
                f"{self._base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise FortyTwoAuthError(f"Token request refused ({resp.status})")
                self._raise_for_status(resp)
                body = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise FortyTwoConnectionError(str(err)) from err

        token = body.get("access_token")
        if not token:
            raise FortyTwoError("Token response without access_token")
        self._token = token
        self._token_expires = (
            time.monotonic() + float(body.get("expires_in", 7200)) - TOKEN_MARGIN
        )
        # Not documented publicly; only used when the API provides it.
        valid_until = body.get("secret_valid_until")
        self.secret_valid_until = (
            datetime.fromtimestamp(valid_until, UTC)
            if isinstance(valid_until, (int, float))
            else None
        )

    async def _async_get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """GET a JSON resource, renewing the token once if it was refused."""
        for attempt in range(2):
            if self._token is None or time.monotonic() >= self._token_expires:
                await self.async_authenticate()
            try:
                async with self._session.get(
                    f"{self._base_url}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        self._token = None
                        continue
                    if resp.status == 401:
                        raise FortyTwoAuthError("Access token refused")
                    self._raise_for_status(resp)
                    return await resp.json()
            except (aiohttp.ClientError, TimeoutError) as err:
                raise FortyTwoConnectionError(str(err)) from err
        raise FortyTwoAuthError("Access token refused")  # pragma: no cover

    @staticmethod
    def _raise_for_status(resp: aiohttp.ClientResponse) -> None:
        if resp.status < 400:
            return
        if resp.status == 404:
            raise FortyTwoNotFoundError(f"Not found: {resp.url.path}")
        if resp.status == 429:
            raise FortyTwoRateLimitError("Rate limit reached")
        if resp.status >= 500:
            raise FortyTwoConnectionError(f"Server error {resp.status}")
        raise FortyTwoError(f"Unexpected status {resp.status}")

    async def async_get_user(self, user: str | int) -> dict[str, Any]:
        """Return a user by login or id."""
        return await self._async_get(f"/v2/users/{user}")

    async def async_get_logtime(
        self, user: str | int, begin: date, end: date, time_zone: str | None = None
    ) -> dict[date, timedelta]:
        """Return the logtime per day from ``begin`` to ``end`` (both included)."""
        params = {
            "begin_at": begin.isoformat(),
            # end_at is exclusive.
            "end_at": (end + timedelta(days=1)).isoformat(),
        }
        if time_zone:
            params["time_zone"] = time_zone
        raw = await self._async_get(f"/v2/users/{user}/locations_stats", params)
        return {
            date.fromisoformat(day): parse_duration(value)
            for day, value in (raw or {}).items()
        }
