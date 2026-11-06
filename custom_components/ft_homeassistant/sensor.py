"""Sensors for the 42 Intra integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FortyTwoConfigEntry, FortyTwoCoordinator, FortyTwoData
from .entity import FortyTwoEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FortyTwoSensorDescription(SensorEntityDescription):
    """Describe a 42 sensor."""

    value_fn: Callable[[FortyTwoData], Any]
    attrs_fn: Callable[[FortyTwoData], dict[str, Any]] | None = None


def _hours(data: FortyTwoData, attr: str) -> float:
    return round(getattr(data, attr).total_seconds() / 3600, 2)


def _level_attrs(data: FortyTwoData) -> dict[str, Any]:
    cursus = data.main_cursus or {}
    return {
        "cursus": (cursus.get("cursus") or {}).get("name"),
        "grade": cursus.get("grade"),
    }


LOGTIME_SENSORS = tuple(
    FortyTwoSensorDescription(
        key=f"logtime_{period}",
        translation_key=f"logtime_{period}",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
        value_fn=lambda data, attr=f"logtime_{period}": _hours(data, attr),
    )
    for period in ("today", "week", "month")
)

SENSORS: tuple[FortyTwoSensorDescription, ...] = (
    *LOGTIME_SENSORS,
    FortyTwoSensorDescription(
        key="location",
        translation_key="location",
        value_fn=lambda data: data.location,
    ),
    FortyTwoSensorDescription(
        key="level",
        translation_key="level",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: (data.main_cursus or {}).get("level"),
        attrs_fn=_level_attrs,
    ),
    FortyTwoSensorDescription(
        key="wallet",
        translation_key="wallet",
        native_unit_of_measurement="₳",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.user.get("wallet"),
    ),
    FortyTwoSensorDescription(
        key="evaluation_points",
        translation_key="evaluation_points",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.user.get("correction_point"),
    ),
)

SECRET_EXPIRY_SENSOR = FortyTwoSensorDescription(
    key="secret_expiry",
    translation_key="secret_expiry",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda data: data.secret_valid_until,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FortyTwoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    descriptions = list(SENSORS)
    # Only when the API reports when the application secret expires.
    if coordinator.data.secret_valid_until is not None:
        descriptions.append(SECRET_EXPIRY_SENSOR)
    async_add_entities(FortyTwoSensor(coordinator, d) for d in descriptions)


class FortyTwoSensor(FortyTwoEntity, SensorEntity):
    """A 42 sensor."""

    entity_description: FortyTwoSensorDescription

    def __init__(
        self, coordinator: FortyTwoCoordinator, description: FortyTwoSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | float | datetime | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
