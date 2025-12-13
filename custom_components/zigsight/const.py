"""Constants for the ZigSight integration."""

DOMAIN = "zigsight"

# Configuration keys
CONF_INTEGRATION_TYPE = "integration_type"
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
CONF_MQTT_BROKER = "mqtt_broker"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"  # nosec B105 - configuration key label
CONF_RECONNECT_THRESHOLD = "reconnect_threshold"
CONF_RETENTION_DAYS = "retention_days"
CONF_ENABLE_ZHA = "enable_zha"

# Integration types
INTEGRATION_TYPE_ZHA = "zha"
INTEGRATION_TYPE_ZIGBEE2MQTT = "zigbee2mqtt"

# Default values
DEFAULT_INTEGRATION_TYPE = INTEGRATION_TYPE_ZIGBEE2MQTT
DEFAULT_MQTT_TOPIC_PREFIX = "zigbee2mqtt"
DEFAULT_MQTT_BROKER = "localhost"
DEFAULT_MQTT_PORT = 1883
DEFAULT_RECONNECT_THRESHOLD = 5
DEFAULT_RETENTION_DAYS = 30
DEFAULT_ENABLE_ZHA = False

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
