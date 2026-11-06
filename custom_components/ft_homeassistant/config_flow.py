"""Config flow for the 42 Intra integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    FortyTwoApiClient,
    FortyTwoAuthError,
    FortyTwoConnectionError,
    FortyTwoError,
    FortyTwoNotFoundError,
)
from .const import (
    APPS_URL,
    CONF_LOGIN,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import FortyTwoConfigEntry

SECRET_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): SECRET_SELECTOR,
        vol.Required(CONF_LOGIN): str,
    }
)


async def _validate(
    hass: HomeAssistant, client_id: str, client_secret: str, user: str | int
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Check the credentials and the user, return (user, errors)."""
    client = FortyTwoApiClient(async_get_clientsession(hass), client_id, client_secret)
    try:
        return await client.async_get_user(user), {}
    except FortyTwoAuthError:
        return None, {"base": "invalid_auth"}
    except FortyTwoNotFoundError:
        return None, {CONF_LOGIN: "user_not_found"}
    except FortyTwoConnectionError:
        return None, {"base": "cannot_connect"}
    except FortyTwoError:
        LOGGER.exception("Unexpected error from the 42 API")
        return None, {"base": "unknown"}


class FortyTwoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 42 Intra."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(entry: FortyTwoConfigEntry) -> FortyTwoOptionsFlow:
        """Return the options flow."""
        return FortyTwoOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API application credentials and the student login."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            client_secret = user_input[CONF_CLIENT_SECRET].strip()
            login = user_input[CONF_LOGIN].strip().lower()
            user, errors = await _validate(self.hass, client_id, client_secret, login)
            if user is not None:
                await self.async_set_unique_id(str(user["id"]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user.get("login", login),
                    data={
                        CONF_CLIENT_ID: client_id,
                        CONF_CLIENT_SECRET: client_secret,
                        CONF_LOGIN: user.get("login", login),
                        CONF_USER_ID: user["id"],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA,
                {k: v for k, v in (user_input or {}).items() if k != CONF_CLIENT_SECRET},
            ),
            errors=errors,
            description_placeholders={"apps_url": APPS_URL},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication when the secret is refused or about to expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new application credentials."""
        entry = self._get_reauth_entry()
        return await self._async_credentials_step(
            "reauth_confirm", entry, user_input, require_secret=True
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the application credentials."""
        entry = self._get_reconfigure_entry()
        return await self._async_credentials_step(
            "reconfigure", entry, user_input, require_secret=False
        )

    async def _async_credentials_step(
        self,
        step_id: str,
        entry: FortyTwoConfigEntry,
        user_input: dict[str, Any] | None,
        *,
        require_secret: bool,
    ) -> ConfigFlowResult:
        """Shared form for reauth and reconfigure (an empty secret keeps the current one)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            client_secret = (
                user_input.get(CONF_CLIENT_SECRET) or ""
            ).strip() or entry.data[CONF_CLIENT_SECRET]
            user, errors = await _validate(
                self.hass, client_id, client_secret, entry.data[CONF_USER_ID]
            )
            if user is not None:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_CLIENT_ID: client_id,
                        CONF_CLIENT_SECRET: client_secret,
                    },
                )
        secret_key = (
            vol.Required(CONF_CLIENT_SECRET)
            if require_secret
            else vol.Optional(CONF_CLIENT_SECRET)
        )
        schema = vol.Schema(
            {vol.Required(CONF_CLIENT_ID): str, secret_key: SECRET_SELECTOR}
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {CONF_CLIENT_ID: (user_input or entry.data)[CONF_CLIENT_ID]},
            ),
            errors=errors,
            description_placeholders={
                "apps_url": APPS_URL,
                "login": entry.data[CONF_LOGIN],
            },
        )


class FortyTwoOptionsFlow(OptionsFlowWithReload):
    """Options for 42 Intra."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
        )
