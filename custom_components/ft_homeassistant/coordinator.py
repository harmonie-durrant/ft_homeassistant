"""Data update coordinator for the 42 Intra integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    FortyTwoApiClient,
    FortyTwoAuthError,
    FortyTwoError,
    FortyTwoRateLimitError,
)
from .const import (
    CONF_LOGIN,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAIN_CURSUS_ID,
    SECRET_EXPIRY_WARNING,
)

type FortyTwoConfigEntry = ConfigEntry[FortyTwoCoordinator]


@dataclass(slots=True)
class FortyTwoData:
    """What one refresh returns."""

    user: dict[str, Any]
    logtime: dict[date, timedelta]
    today: date
    secret_valid_until: datetime | None

    def logtime_since(self, start: date) -> timedelta:
        """Total logtime from ``start`` to today (both included)."""
        return sum(
            (v for d, v in self.logtime.items() if start <= d <= self.today),
            timedelta(),
        )

    @property
    def logtime_today(self) -> timedelta:
        return self.logtime_since(self.today)

    @property
    def logtime_week(self) -> timedelta:
        return self.logtime_since(self.today - timedelta(days=self.today.weekday()))

    @property
    def logtime_month(self) -> timedelta:
        return self.logtime_since(self.today.replace(day=1))

    @property
    def location(self) -> str | None:
        return self.user.get("location") or None

    @property
    def main_cursus(self) -> dict[str, Any] | None:
        """The main 42 cursus, else the most recently started one."""
        cursus_users = self.user.get("cursus_users") or []
        for cursus_user in cursus_users:
            if cursus_user.get("cursus_id") == MAIN_CURSUS_ID:
                return cursus_user
        return max(
            cursus_users, key=lambda c: c.get("begin_at") or "", default=None
        )


def mask(value: str) -> str:
    """Mask a secret or identifier for logs."""
    return f"…{value[-4:]}" if len(value) > 4 else "…"


class FortyTwoCoordinator(DataUpdateCoordinator[FortyTwoData]):
    """Fetch the profile and logtime of one student."""

    config_entry: FortyTwoConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FortyTwoConfigEntry) -> None:
        """Initialize the coordinator."""
        minutes = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_LOGIN]}",
            update_interval=timedelta(minutes=minutes),
        )
        self.client = FortyTwoApiClient(
            async_get_clientsession(hass),
            entry.data[CONF_CLIENT_ID],
            entry.data[CONF_CLIENT_SECRET],
        )
        self.user_id: int = entry.data[CONF_USER_ID]
        self.login: str = entry.data[CONF_LOGIN]

    async def _async_update_data(self) -> FortyTwoData:
        today = dt_util.now().date()
        begin = min(today.replace(day=1), today - timedelta(days=today.weekday()))
        try:
            user = await self.client.async_get_user(self.user_id)
            logtime = await self.client.async_get_logtime(
                self.user_id, begin, today, self.hass.config.time_zone
            )
        except FortyTwoAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except FortyTwoRateLimitError as err:
            if self.data is not None:
                LOGGER.warning("42 API rate limit reached, keeping the last data")
                return self.data
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="rate_limited"
            ) from err
        except FortyTwoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        LOGGER.debug(
            "Fetched %s (id %s): location=%s, %d logtime days since %s",
            self.login,
            mask(str(self.user_id)),
            user.get("location"),
            len(logtime),
            begin,
        )
        data = FortyTwoData(
            user=user,
            logtime=logtime,
            today=today,
            secret_valid_until=self.client.secret_valid_until,
        )
        self._check_secret_expiry(data.secret_valid_until)
        return data

    def _check_secret_expiry(self, valid_until: datetime | None) -> None:
        """Ask for a new secret a few days before the current one expires."""
        if valid_until and valid_until - dt_util.utcnow() < SECRET_EXPIRY_WARNING:
            LOGGER.info("The 42 application secret expires on %s", valid_until)
            self.config_entry.async_start_reauth(self.hass)
