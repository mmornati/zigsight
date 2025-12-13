"""ZHA collector for ZigSight."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


class ZHACollector:
    """Collector for ZHA device diagnostics."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ZHA collector."""
        self.hass = hass
        self._device_registry = dr.async_get(hass)
        self._entity_registry = er.async_get(hass)

    def is_available(self) -> bool:
        """Check if ZHA integration is available."""
        return "zha" in self.hass.data

    async def collect_devices(self) -> dict[str, dict[str, Any]]:
        """Collect device information from ZHA.

        Returns:
            Dictionary of device_id -> device_data with normalized metrics.
        """
        if not self.is_available():
            _LOGGER.debug("ZHA integration not available")
            return {}

        devices = {}
        zha_data = self.hass.data.get("zha")
        if not zha_data:
            return {}

        # Get ZHA gateway
        gateway = zha_data.get("gateway")
        if not gateway:
            _LOGGER.warning("ZHA gateway not found")
            return {}

        # Get all ZHA devices
        try:
            zha_devices = gateway.devices
        except AttributeError:
            _LOGGER.warning("Unable to access ZHA devices")
            return {}

        for ieee, zha_device in zha_devices.items():
            try:
                device_data = await self._collect_device_data(zha_device, ieee)
                if device_data:
                    # Use IEEE address as device ID for consistency
                    device_id = str(ieee)
                    devices[device_id] = device_data
            except Exception as err:
                _LOGGER.debug(
                    "Error collecting data for ZHA device %s: %s", ieee, err
                )

        _LOGGER.debug("Collected %d ZHA devices", len(devices))
        return devices

    async def _collect_device_data(
        self, zha_device: Any, ieee: str
    ) -> dict[str, Any] | None:
        """Collect data for a single ZHA device."""
        try:
            # Get device name
            device_name = getattr(zha_device, "name", None) or str(ieee)

            # Initialize device data
            device_data = {
                "device_id": str(ieee),
                "friendly_name": device_name,
                "ieee": str(ieee),
                "metrics": {},
            }

            # Collect metrics from ZHA device attributes
            metrics = await self._collect_device_metrics(zha_device)
            device_data["metrics"] = metrics

            # Try to get metrics from diagnostic entities
            entity_metrics = await self._collect_entity_metrics(str(ieee))
            device_data["metrics"].update(entity_metrics)

            return device_data

        except Exception as err:
            _LOGGER.debug("Error processing ZHA device %s: %s", ieee, err)
            return None

    async def _collect_device_metrics(self, zha_device: Any) -> dict[str, Any]:
        """Collect metrics from ZHA device attributes."""
        metrics = {}

        try:
            # Get last_seen from device
            last_seen = getattr(zha_device, "last_seen", None)
            if last_seen:
                metrics["last_seen"] = last_seen.isoformat() if hasattr(
                    last_seen, "isoformat"
                ) else str(last_seen)
            else:
                metrics["last_seen"] = datetime.now().isoformat()

            # Get LQI (Link Quality Indicator) - ZHA's equivalent of link_quality
            lqi = getattr(zha_device, "lqi", None)
            if lqi is not None:
                # ZHA LQI is 0-255, normalize to match Zigbee2MQTT range
                metrics["link_quality"] = lqi

            # Get RSSI if available
            rssi = getattr(zha_device, "rssi", None)
            if rssi is not None:
                metrics["rssi"] = rssi

            # Try to get device info for additional attributes
            device_info = getattr(zha_device, "device_info", None)
            if device_info:
                # Extract power source information
                power_source = device_info.get("power_source")
                if power_source:
                    metrics["power_source"] = power_source

        except Exception as err:
            _LOGGER.debug("Error collecting device metrics: %s", err)

        return metrics

    async def _collect_entity_metrics(self, ieee: str) -> dict[str, Any]:
        """Collect metrics from ZHA diagnostic entities.

        ZHA creates diagnostic entities like:
        - sensor.<device>_rssi
        - sensor.<device>_lqi
        - sensor.<device>_last_seen
        """
        metrics = {}

        # Find device in registry using identifiers
        device_entry = self._device_registry.async_get_device(
            identifiers={("zha", ieee)}
        )

        if not device_entry:
            return metrics

        # Find entities for this device
        entities = er.async_entries_for_device(
            self._entity_registry, device_entry.id, include_disabled_entities=True
        )

        for entity in entities:
            try:
                # Get entity state
                state = self.hass.states.get(entity.entity_id)
                if not state or state.state in ("unknown", "unavailable"):
                    continue

                # Extract metric based on entity type
                if "rssi" in entity.entity_id.lower():
                    try:
                        metrics["rssi"] = int(float(state.state))
                    except (ValueError, TypeError):
                        pass
                elif "lqi" in entity.entity_id.lower() or "link_quality" in entity.entity_id.lower():
                    try:
                        metrics["link_quality"] = int(float(state.state))
                    except (ValueError, TypeError):
                        pass
                elif "battery" in entity.entity_id.lower() and entity.domain == "sensor":
                    try:
                        battery_value = float(state.state)
                        metrics["battery"] = battery_value
                    except (ValueError, TypeError):
                        pass

            except Exception as err:
                _LOGGER.debug(
                    "Error reading entity %s: %s", entity.entity_id, err
                )

        return metrics
