"""Constants for the ZigSight integration."""

DOMAIN = "zigsight"

# Configuration keys
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
CONF_RECONNECT_THRESHOLD = "reconnect_threshold"
CONF_RETENTION_DAYS = "retention_days"

# Default values
DEFAULT_MQTT_TOPIC_PREFIX = "zigbee2mqtt"
DEFAULT_RECONNECT_THRESHOLD = 5
DEFAULT_RETENTION_DAYS = 30

# Event types
EVENT_DEVICE_UPDATE = "zigsight_device_update"

# Sensor attributes
ATTR_DEVICE_ID = "device_id"
ATTR_METRICS = "metrics"
ATTR_LINK_QUALITY = "link_quality"
ATTR_BATTERY = "battery"
ATTR_VOLTAGE = "voltage"
ATTR_LAST_SEEN = "last_seen"
ATTR_RECONNECT_RATE = "reconnect_rate"
