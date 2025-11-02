"""DataUpdateCoordinator for ZigSight."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MQTT_TOPIC_PREFIX,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DOMAIN,
    EVENT_DEVICE_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


class ZigSightCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching ZigSight data from Zigbee2MQTT."""

    def __init__(
        self,
        hass: HomeAssistant,
        mqtt_prefix: str = DEFAULT_MQTT_TOPIC_PREFIX,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._mqtt_prefix = mqtt_prefix
        self._devices: dict[str, dict[str, Any]] = {}
        self._device_history: dict[str, list[dict[str, Any]]] = {}
        self._unsub_mqtt: list[Any] = []

    async def async_start(self) -> None:
        """Start the coordinator and subscribe to MQTT topics."""
        self.logger.info(
            "Starting ZigSight coordinator with MQTT prefix: %s", self._mqtt_prefix
        )

        # Subscribe to Zigbee2MQTT bridge state
        bridge_topic = f"{self._mqtt_prefix}/bridge/state"
        await self._subscribe_mqtt(bridge_topic, self._on_bridge_state)

        # Subscribe to all device updates
        devices_topic = f"{self._mqtt_prefix}/#"
        await self._subscribe_mqtt(devices_topic, self._on_device_message)

    async def _subscribe_mqtt(self, topic: str, callback: Any) -> None:
        """Subscribe to an MQTT topic."""
        try:
            unsub = await mqtt.async_subscribe(
                self.hass,
                topic,
                callback,
                0,
            )
            if unsub:
                self._unsub_mqtt.append(unsub)
                self.logger.debug("Subscribed to MQTT topic: %s", topic)
        except Exception as err:
            self.logger.error(
                "Failed to subscribe to MQTT topic %s: %s", topic, err
            )

    @callback
    def _on_bridge_state(self, msg: mqtt.ReceiveMessage) -> None:
        """Handle bridge state messages."""
        try:
            payload = msg.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            
            state_data = json.loads(payload) if isinstance(payload, str) else payload
            self.logger.debug("Bridge state update: %s", state_data)
            
            # Store bridge state for future use
            self._devices["bridge"] = {"state": state_data, "last_update": datetime.now().isoformat()}
        except Exception as err:
            self.logger.error("Error processing bridge state: %s", err)

    @callback
    def _on_device_message(self, msg: mqtt.ReceiveMessage) -> None:
        """Handle device update messages."""
        try:
            topic_parts = msg.topic.split("/")
            if len(topic_parts) < 2:
                return

            # Topic format: <prefix>/<device_id> or <prefix>/<device_id>/set
            device_id = topic_parts[1]

            # Skip bridge messages (already handled)
            if device_id == "bridge":
                return

            payload = msg.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            device_data = json.loads(payload) if isinstance(payload, str) else payload

            # Process device update
            self._process_device_update(device_id, device_data, msg.topic)
            
            # Notify listeners about the update
            self.async_update_listeners()

        except Exception as err:
            self.logger.error("Error processing device message: %s", err)

    def _process_device_update(
        self, device_id: str, data: dict[str, Any], topic: str
    ) -> None:
        """Process a device update and store metrics."""
        now = datetime.now()

        # Extract device metrics
        metrics = {
            "link_quality": data.get("linkquality", data.get("link_quality")),
            "battery": data.get("battery", data.get("battery_percent")),
            "voltage": data.get("voltage"),
            "last_seen": now.isoformat(),
            "last_message": data,
        }
        
        # Initialize device entry if not exists
        if device_id not in self._devices:
            self._devices[device_id] = {
                "device_id": device_id,
                "friendly_name": data.get("friendly_name", device_id),
                "first_seen": now.isoformat(),
                "reconnect_count": 0,
                "last_reconnect": None,
            }

        # Check for reconnections
        device = self._devices[device_id]
        last_seen_str = device.get("metrics", {}).get("last_seen")
        if last_seen_str:
            try:
                last_seen = datetime.fromisoformat(last_seen_str)
                time_diff = (now - last_seen).total_seconds()
                # If more than 5 minutes since last update, consider it a reconnect
                if time_diff > 300:
                    device["reconnect_count"] = device.get("reconnect_count", 0) + 1
                    device["last_reconnect"] = now.isoformat()
            except (ValueError, TypeError):
                pass

        # Update device metrics
        device["metrics"] = metrics
        device["last_update"] = now.isoformat()
        device["friendly_name"] = data.get(
            "friendly_name", device.get("friendly_name", device_id)
        )

        # Store in history
        if device_id not in self._device_history:
            self._device_history[device_id] = []

        self._device_history[device_id].append(
            {
                "timestamp": now.isoformat(),
                "metrics": metrics.copy(),
            }
        )
        
        # Keep only last 1000 entries per device
        if len(self._device_history[device_id]) > 1000:
            self._device_history[device_id] = self._device_history[device_id][-1000:]

        # Fire event for device update
        self.hass.bus.async_fire(
            EVENT_DEVICE_UPDATE,
            {
                "device_id": device_id,
                "metrics": metrics,
            },
        )

        self.logger.debug("Updated device %s: %s", device_id, metrics)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from ZigSight.

        Returns a dictionary of device_id -> device_data for quick lookup.
        """
        try:
            # Data is updated via MQTT callbacks, so we just return current state
            return {
                "devices": self._devices.copy(),
                "device_count": len(self._devices),
                "last_update": datetime.now().isoformat(),
            }
        except Exception as err:
            raise UpdateFailed(f"Error fetching ZigSight data: {err}") from err

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        """Get device data by device ID."""
        return self._devices.get(device_id)

    def get_device_metrics(self, device_id: str) -> dict[str, Any] | None:
        """Get current metrics for a device."""
        device = self.get_device(device_id)
        if device:
            return device.get("metrics")
        return None

    def get_device_history(self, device_id: str) -> list[dict[str, Any]]:
        """Get history for a device."""
        return self._device_history.get(device_id, [])

    async def async_shutdown(self) -> None:
        """Cancel any background tasks and unsubscribe from MQTT."""
        self.logger.info("Shutting down ZigSight coordinator")

        # Unsubscribe from MQTT
        for unsub in self._unsub_mqtt:
            if unsub:
                unsub()
        self._unsub_mqtt.clear()

        # Cancel any pending tasks
        if hasattr(self, "_tasks"):
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
