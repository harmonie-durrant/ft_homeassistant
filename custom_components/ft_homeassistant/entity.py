"""Base entity for the 42 Intra integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PROFILE_URL
from .coordinator import FortyTwoCoordinator


class FortyTwoEntity(CoordinatorEntity[FortyTwoCoordinator]):
    """An entity attached to one student's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FortyTwoCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.user_id}_{key}"
        user = coordinator.data.user
        campus = next(iter(user.get("campus") or []), {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.user_id))},
            name=user.get("displayname") or coordinator.login,
            manufacturer="42",
            model=campus.get("name") or "Student",
            configuration_url=PROFILE_URL.format(login=coordinator.login),
            entry_type=DeviceEntryType.SERVICE,
        )
