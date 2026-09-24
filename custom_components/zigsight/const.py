"""Constants for the ZigSight integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "zigsight"

# Config entry versioning (see async_migrate_entry in __init__.py).
# 1.1 -> 1.2: removed the direct-MQTT broker settings (mqtt_broker,
#            mqtt_port, mqtt_username, mqtt_password) and the legacy
#            enable_zha flag; Zigbee2MQTT now always goes through Home
#            Assistant's MQTT integration.
CONFIG_ENTRY_VERSION = 1
CONFIG_ENTRY_MINOR_VERSION = 2

# Configuration keys
CONF_INTEGRATION_TYPE = "integration_type"
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"

# Legacy configuration keys, only referenced by the config entry migration.
CONF_ENABLE_ZHA = "enable_zha"
LEGACY_CONF_MQTT_BROKER = "mqtt_broker"
LEGACY_CONF_MQTT_PORT = "mqtt_port"
LEGACY_CONF_MQTT_USERNAME = "mqtt_username"
LEGACY_CONF_MQTT_PASSWORD = "mqtt_password"  # nosec B105 - configuration key label
LEGACY_MQTT_KEYS = (
    LEGACY_CONF_MQTT_BROKER,
    LEGACY_CONF_MQTT_PORT,
    LEGACY_CONF_MQTT_USERNAME,
    LEGACY_CONF_MQTT_PASSWORD,
)

# Integration types
INTEGRATION_TYPE_ZHA = "zha"
INTEGRATION_TYPE_ZIGBEE2MQTT = "zigbee2mqtt"

# Default values
DEFAULT_INTEGRATION_TYPE = INTEGRATION_TYPE_ZIGBEE2MQTT
DEFAULT_MQTT_TOPIC_PREFIX = "zigbee2mqtt"

# Event types
EVENT_DEVICE_UPDATE = "zigsight_device_update"
# The device update event is rate limited per device: it is fired when the
# availability changes, or when a tracked metric changed and at least this
# long has passed since the previous event for that device.
EVENT_MIN_INTERVAL = timedelta(seconds=60)

# Dispatcher signals (formatted with the config entry id / device IEEE).
SIGNAL_NEW_DEVICE = f"{DOMAIN}_new_device_{{entry_id}}"
SIGNAL_DEVICE_UPDATE = f"{DOMAIN}_device_update_{{entry_id}}_{{ieee}}"
SIGNAL_DEVICE_REMOVED = f"{DOMAIN}_device_removed_{{entry_id}}"

# Sensor attributes
ATTR_DEVICE_ID = "device_id"
ATTR_METRICS = "metrics"
ATTR_LINK_QUALITY = "link_quality"
ATTR_BATTERY = "battery"
ATTR_VOLTAGE = "voltage"
ATTR_LAST_SEEN = "last_seen"
ATTR_RECONNECT_RATE = "reconnect_rate"
ATTR_BATTERY_TREND = "battery_trend"
ATTR_HEALTH_SCORE = "health_score"
ATTR_BATTERY_DRAIN_WARNING = "battery_drain_warning"
ATTR_CONNECTIVITY_WARNING = "connectivity_warning"

# Analytics thresholds
CONF_BATTERY_DRAIN_THRESHOLD = "battery_drain_threshold"
CONF_RECONNECT_RATE_THRESHOLD = "reconnect_rate_threshold"
CONF_RECONNECT_RATE_WINDOW_HOURS = "reconnect_rate_window_hours"

DEFAULT_BATTERY_DRAIN_THRESHOLD = 10.0  # percentage per hour
DEFAULT_RECONNECT_RATE_THRESHOLD = 5.0  # events per hour
DEFAULT_RECONNECT_RATE_WINDOW_HOURS = 24  # hours

# Connectivity timeouts used when Zigbee2MQTT availability is not enabled
# (mirrors Zigbee2MQTT's own availability defaults: "active" devices, i.e.
# routers / mains powered, 10 minutes; "passive" devices, i.e. sleepy
# battery end devices, 1500 minutes = 25 hours). When Zigbee2MQTT publishes
# its availability configuration in bridge/info, those values win.
ROUTER_CONNECTIVITY_TIMEOUT = timedelta(minutes=10)
END_DEVICE_CONNECTIVITY_TIMEOUT = timedelta(hours=25)

# Analytics are recomputed at most this often per device when messages
# arrive; the coordinator's periodic refresh recomputes every device anyway.
ANALYTICS_MIN_INTERVAL = timedelta(seconds=30)

# Bounded in-memory history (numeric metrics only).
HISTORY_MAX_ENTRIES = 400
# A history point is recorded at most every HISTORY_MIN_INTERVAL, or after
# HISTORY_MIN_INTERVAL_ON_BATTERY_CHANGE when the battery value changed.
HISTORY_MIN_INTERVAL = timedelta(minutes=5)
HISTORY_MIN_INTERVAL_ON_BATTERY_CHANGE = timedelta(seconds=60)
RECONNECT_EVENTS_MAX = 200

# Coordinator refresh interval (analytics recomputation + ZHA polling).
UPDATE_INTERVAL = timedelta(seconds=60)

# Device source types
DEVICE_SOURCE_ZHA = "zha"
DEVICE_SOURCE_ZIGBEE2MQTT = "zigbee2mqtt"
DEVICE_SOURCE_DECONZ = "deconz"
DEVICE_SOURCE_UNKNOWN = "unknown"

# Zigbee device types (as reported by Zigbee2MQTT bridge/devices)
DEVICE_TYPE_COORDINATOR = "Coordinator"
DEVICE_TYPE_ROUTER = "Router"
DEVICE_TYPE_END_DEVICE = "EndDevice"
