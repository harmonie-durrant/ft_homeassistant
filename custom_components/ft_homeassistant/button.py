"""Buttons for the 42 Intra integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FortyTwoConfigEntry
from .entity import FortyTwoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FortyTwoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    async_add_entities([FortyTwoRefreshButton(entry.runtime_data, "refresh")])


class FortyTwoRefreshButton(FortyTwoEntity, ButtonEntity):
    """Fetch fresh data now."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Refresh the data."""
        await self.coordinator.async_refresh()
