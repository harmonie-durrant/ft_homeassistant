"""Binary sensors for the 42 Intra integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FortyTwoConfigEntry
from .entity import FortyTwoEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FortyTwoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    async_add_entities([FortyTwoLoggedInSensor(entry.runtime_data, "logged_in")])


class FortyTwoLoggedInSensor(FortyTwoEntity, BinarySensorEntity):
    """On when the student is logged in on a campus computer."""

    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    @property
    def is_on(self) -> bool:
        """Return True when logged in."""
        return self.coordinator.data.location is not None
