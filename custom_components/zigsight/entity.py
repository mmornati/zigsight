"""Base entity and dynamic platform setup for ZigSight."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZigSightCoordinator


class ZigSightDeviceEntity(CoordinatorEntity[ZigSightCoordinator]):
    """An entity attached to one Zigbee device (identified by IEEE address).

    State is written when the device's own dispatcher signal fires (a message
    for that device arrived) and on the coordinator's periodic refresh.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        ieee: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._ieee = ieee
        self._attr_unique_id = f"{ieee}_{description.key}"
        self._attr_device_info = coordinator.device_info(ieee)

    @property
    def ieee(self) -> str:
        """Return the IEEE address of the device."""
        return self._ieee

    @property
    def available(self) -> bool:
        """Return True while the device is tracked and enabled."""
        return super().available and self.coordinator.wants_entities(self._ieee)

    async def async_added_to_hass(self) -> None:
        """Subscribe to per-device updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.coordinator.device_signal(self._ieee),
                self._handle_device_update,
            )
        )

    @callback
    def _handle_device_update(self) -> None:
        self.async_write_ha_state()


def async_setup_device_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    build_entities: Callable[[ZigSightCoordinator, str], Iterable[Entity]],
) -> None:
    """Add entities for known devices now and for new devices later.

    The coordinator sends ``signal_new_device`` whenever a device may need
    entities: first seen, interview completed, capabilities changed (e.g. a
    battery expose appeared) or re-enabled in Zigbee2MQTT. Entities are
    tracked per unique id, so only the missing ones are added; a removed
    device forgets its entities so they are recreated if it re-joins.
    """
    coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]
    added: set[str] = set()

    @callback
    def _async_add(ieees: Iterable[str]) -> None:
        entities: list[Entity] = []
        for ieee in ieees:
            if not coordinator.wants_entities(ieee):
                continue
            for entity in build_entities(coordinator, ieee):
                if entity.unique_id is None or entity.unique_id in added:
                    continue
                added.add(entity.unique_id)
                entities.append(entity)
        if entities:
            async_add_entities(entities)

    @callback
    def _async_new_device(ieee: str) -> None:
        _async_add([ieee])

    @callback
    def _async_device_removed(ieee: str) -> None:
        prefix = f"{ieee}_"
        added.difference_update(
            [unique_id for unique_id in added if unique_id.startswith(prefix)]
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, coordinator.signal_new_device, _async_new_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, coordinator.signal_device_removed, _async_device_removed
        )
    )
    _async_add(coordinator.device_ids())
