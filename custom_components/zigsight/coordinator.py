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

from .analytics import DeviceAnalytics
from .const import (
    CONF_MQTT_BROKER,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_MQTT_USERNAME,
    DEFAULT_BATTERY_DRAIN_THRESHOLD,
    DEFAULT_MQTT_BROKER,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
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
        mqtt_broker: str | None = None,
        mqtt_port: int | None = None,
        mqtt_username: str | None = None,
        mqtt_password: str | None = None,
        battery_drain_threshold: float = DEFAULT_BATTERY_DRAIN_THRESHOLD,
        reconnect_rate_threshold: float = DEFAULT_RECONNECT_RATE_THRESHOLD,
        reconnect_rate_window_hours: int = DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._mqtt_prefix = mqtt_prefix
        self._mqtt_broker = mqtt_broker or DEFAULT_MQTT_BROKER
        self._mqtt_port = mqtt_port or DEFAULT_MQTT_PORT
        self._mqtt_username = mqtt_username
        self._mqtt_password = mqtt_password
        self._use_direct_mqtt = bool(mqtt_broker and mqtt_port)
        self._devices: dict[str, dict[str, Any]] = {}
        self._device_history: dict[str, list[dict[str, Any]]] = {}
        self._unsub_mqtt: list[Any] = []
        self._mqtt_client_task: asyncio.Task[None] | None = None
        self._mqtt_callbacks: dict[str, list[Any]] = {}
        self._analytics = DeviceAnalytics(
            reconnect_rate_window_hours=reconnect_rate_window_hours,
            battery_drain_threshold=battery_drain_threshold,
        )
        self._reconnect_rate_threshold = reconnect_rate_threshold

    async def async_start(self) -> None:
        """Start the coordinator and subscribe to MQTT topics."""
        self.logger.info(
            "Starting ZigSight coordinator with MQTT prefix: %s", self._mqtt_prefix
        )

        if self._use_direct_mqtt:
            # Start direct MQTT client connection
            await self._start_direct_mqtt()

        # Subscribe to Zigbee2MQTT bridge state
        bridge_topic = f"{self._mqtt_prefix}/bridge/state"
        await self._subscribe_mqtt(bridge_topic, self._on_bridge_state)

        # Subscribe to all device updates
        devices_topic = f"{self._mqtt_prefix}/#"
        await self._subscribe_mqtt(devices_topic, self._on_device_message)

    async def _start_direct_mqtt(self) -> None:
        """Start direct MQTT client connection."""
        try:
            from aiomqtt import Client as MQTTClient
            from aiomqtt.exceptions import MqttError
        except ImportError:
            self.logger.error(
                "aiomqtt not available. Install it with: pip install aiomqtt"
            )
            raise

        self.logger.info(
            "Connecting to MQTT broker %s:%s with %s",
            self._mqtt_broker,
            self._mqtt_port,
            "authentication" if self._mqtt_username else "no authentication",
        )

        async def mqtt_client_task() -> None:
            """Task to handle MQTT client connection and messages."""
            while True:
                try:
                    async with MQTTClient(
                        hostname=self._mqtt_broker,
                        port=self._mqtt_port,
                        username=self._mqtt_username if self._mqtt_username else None,
                        password=self._mqtt_password if self._mqtt_password else None,
                    ) as client:
                        self.logger.info("Connected to MQTT broker")
                        # Subscribe to all topics registered so far
                        for topic in self._mqtt_callbacks:
                            await client.subscribe(topic)
                            self.logger.debug("Subscribed to MQTT topic: %s", topic)

                        async for message in client.messages:
                            # Convert aiomqtt message to Home Assistant format
                            class ReceiveMessage:
                                def __init__(self, topic: str, payload: bytes) -> None:
                                    self.topic = topic
                                    self.payload = payload

                            msg = ReceiveMessage(message.topic, message.payload)
                            # Call all callbacks for matching topic patterns
                            for (
                                topic_pattern,
                                callbacks,
                            ) in self._mqtt_callbacks.items():
                                if self._topic_matches(message.topic, topic_pattern):
                                    for callback in callbacks:
                                        try:
                                            callback(msg)
                                        except Exception as err:
                                            self.logger.error(
                                                "Error in MQTT callback: %s", err
                                            )
                except Exception as err:
                    self.logger.error(
                        "MQTT connection error, reconnecting in 5 seconds: %s", err
                    )
                    await asyncio.sleep(5)

        # Start MQTT client task
        self._mqtt_client_task = asyncio.create_task(mqtt_client_task())

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern (supports # wildcard)."""
        if pattern == "#" or pattern.endswith("/#"):
            prefix = pattern.rstrip("#").rstrip("/")
            return topic.startswith(prefix)
        return topic == pattern

    async def _subscribe_mqtt(self, topic: str, callback: Any) -> None:
        """Subscribe to an MQTT topic."""
        try:
            if self._use_direct_mqtt:
                # Use direct MQTT client connection
                if topic not in self._mqtt_callbacks:
                    self._mqtt_callbacks[topic] = []
                self._mqtt_callbacks[topic].append(callback)
                self.logger.debug("Registered callback for MQTT topic: %s", topic)

                # If client is already running, subscribe to the topic
                if self._mqtt_client_task and not self._mqtt_client_task.done():
                    try:
                        from aiomqtt import Client as MQTTClient

                        # Re-subscribe if client is connected
                        # Note: This requires access to the client, which we'd need to store
                        # For now, reconnection will handle new subscriptions
                        pass
                    except ImportError:
                        pass
            else:
                # Use Home Assistant's MQTT integration
                if not await mqtt.async_wait_for_mqtt_client(self.hass):
                    self.logger.warning(
                        "MQTT client not available, falling back to direct connection"
                    )
                    self._use_direct_mqtt = True
                    self._mqtt_broker = DEFAULT_MQTT_BROKER
                    self._mqtt_port = DEFAULT_MQTT_PORT
                    await self._start_direct_mqtt()
                    await self._subscribe_mqtt(topic, callback)
                    return

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
            self.logger.error("Failed to subscribe to MQTT topic %s: %s", topic, err)
            raise

    @callback
    def _on_bridge_state(self, msg: Any) -> None:  # type: ignore[type-arg]
        """Handle bridge state messages."""
        try:
            payload = msg.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            state_data = json.loads(payload) if isinstance(payload, str) else payload
            self.logger.debug("Bridge state update: %s", state_data)

            # Store bridge state for future use
            self._devices["bridge"] = {
                "state": state_data,
                "last_update": datetime.now().isoformat(),
            }
        except Exception as err:
            self.logger.error("Error processing bridge state: %s", err)

    @callback
    def _on_device_message(self, msg: Any) -> None:  # type: ignore[type-arg]
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

    def get_device_reconnect_rate(self, device_id: str) -> float | None:
        """Get reconnect rate for a device."""
        device_history = self.get_device_history(device_id)
        if not device_history:
            return None
        return self._analytics.compute_reconnect_rate(device_history)

    def get_device_battery_trend(self, device_id: str) -> float | None:
        """Get battery trend for a device."""
        device_history = self.get_device_history(device_id)
        if not device_history:
            return None
        return self._analytics.compute_battery_trend(device_history)

    def get_device_health_score(self, device_id: str) -> float | None:
        """Get health score for a device."""
        device = self.get_device(device_id)
        if not device:
            return None
        device_history = self.get_device_history(device_id)
        return self._analytics.compute_health_score(device, device_history)

    def get_device_battery_drain_warning(self, device_id: str) -> bool:
        """Get battery drain warning status for a device."""
        device_history = self.get_device_history(device_id)
        if not device_history:
            return False
        return self._analytics.check_battery_drain_warning(device_history)

    def get_device_connectivity_warning(self, device_id: str) -> bool:
        """Get connectivity warning status for a device."""
        device = self.get_device(device_id)
        if not device:
            return False
        # Add history to device data for analytics
        device_with_history = device.copy()
        device_with_history["history"] = self.get_device_history(device_id)
        return self._analytics.check_connectivity_warning(
            device_with_history, self._reconnect_rate_threshold
        )

    async def async_shutdown(self) -> None:
        """Cancel any background tasks and unsubscribe from MQTT."""
        self.logger.info("Shutting down ZigSight coordinator")

        # Cancel MQTT client task if using direct connection
        if self._mqtt_client_task and not self._mqtt_client_task.done():
            self._mqtt_client_task.cancel()
            try:
                await self._mqtt_client_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe from MQTT
        for unsub in self._unsub_mqtt:
            if unsub:
                unsub()
        self._unsub_mqtt.clear()
        self._mqtt_callbacks.clear()

        # Cancel any pending tasks
        if hasattr(self, "_tasks"):
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
