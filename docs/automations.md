# ZigSight Automations Guide

This guide explains how to use the ZigSight automation blueprints to monitor your Zigbee network and receive alerts.

## Overview

ZigSight provides three automation blueprints for common monitoring scenarios:

1. **Battery Drain Alert** - Notifies when device batteries fall below a threshold
2. **Reconnect Flap Alert** - Detects devices that frequently disconnect/reconnect
3. **Daily Network Health Report** - Sends a daily summary of your network status

## Importing Blueprints

### Method 1: Home Assistant UI (Recommended)

1. Navigate to **Settings** → **Automations & Scenes** → **Blueprints**
2. Click **Import Blueprint** (bottom right corner)
3. Paste the blueprint URL:

| Blueprint | Import URL |
|-----------|------------|
| Battery Drain | `https://raw.githubusercontent.com/mmornati/zigsight/main/automations/battery_drain.yaml` |
| Reconnect Flap | `https://raw.githubusercontent.com/mmornati/zigsight/main/automations/reconnect_flap.yaml` |
| Daily Report | `https://raw.githubusercontent.com/mmornati/zigsight/main/automations/network_health_daily_report.yaml` |

4. Click **Preview Blueprint**, then **Import Blueprint**

### Method 2: Manual File Copy

Copy the blueprint files to your Home Assistant configuration:

```bash
# Create the blueprint directory
mkdir -p /config/blueprints/automation/zigsight/

# Copy blueprints (from the repository)
cp automations/battery_drain.yaml /config/blueprints/automation/zigsight/
cp automations/reconnect_flap.yaml /config/blueprints/automation/zigsight/
cp automations/network_health_daily_report.yaml /config/blueprints/automation/zigsight/
```

Restart Home Assistant or reload automations to see the new blueprints.

## Creating Automations from Blueprints

### Via Home Assistant UI

1. Go to **Settings** → **Automations & Scenes** → **Automations**
2. Click **Create Automation** → **Use Blueprint**
3. Select the ZigSight blueprint you want to use
4. Configure the inputs as described below
5. Click **Save**

### Via YAML

You can also create automations directly in your `automations.yaml`:

```yaml
# Example: Battery drain alert for a specific device
- id: zigsight_battery_alert_motion_sensor
  alias: "ZigSight: Motion Sensor Battery Alert"
  use_blueprint:
    path: zigsight/battery_drain.yaml
    input:
      battery_sensor: sensor.motion_sensor_battery
      battery_threshold: 20
      notify_service: notify.mobile_app_phone
      notification_title: "Low Battery Alert"
      cooldown_hours: 24

# Example: Reconnect flapping detection
- id: zigsight_flap_alert_door_sensor
  alias: "ZigSight: Door Sensor Flap Alert"
  use_blueprint:
    path: zigsight/reconnect_flap.yaml
    input:
      device_availability: binary_sensor.door_sensor_availability
      reconnect_count_threshold: 5
      time_window_minutes: 60
      notify_service: notify.mobile_app_phone
      cooldown_hours: 6

# Example: Daily network health report
- id: zigsight_daily_report
  alias: "ZigSight: Daily Network Report"
  use_blueprint:
    path: zigsight/network_health_daily_report.yaml
    input:
      report_time: "09:00:00"
      low_battery_threshold: 30
      offline_hours_threshold: 24
      notify_service: notify.mobile_app_phone
      include_healthy_summary: true
      weekdays_only: false
```

## Blueprint Configuration Reference

### Battery Drain Alert

Monitors a battery sensor and sends a notification when the level drops below a threshold.

| Input | Description | Default |
|-------|-------------|---------|
| `battery_sensor` | Battery level sensor entity to monitor | Required |
| `battery_threshold` | Battery percentage trigger threshold | 20% |
| `notify_service` | Notification service (e.g., `notify.mobile_app`) | Empty (uses persistent notification) |
| `notification_title` | Title for the notification | "ZigSight: Low Battery Alert" |
| `cooldown_hours` | Hours between repeated alerts | 24 |

**Example notification:**
> Motion Sensor battery is low at 15%. Consider replacing the battery soon.

### Reconnect Flap Alert

Detects devices that reconnect too frequently, which may indicate interference or connectivity issues.

| Input | Description | Default |
|-------|-------------|---------|
| `device_availability` | Availability or connectivity entity | Required |
| `reconnect_count_threshold` | Number of reconnects to trigger alert | 5 |
| `time_window_minutes` | Time window for counting reconnects | 60 |
| `notify_service` | Notification service | Empty (uses persistent notification) |
| `notification_title` | Title for the notification | "ZigSight: Device Flapping Detected" |
| `cooldown_hours` | Hours between repeated alerts | 6 |

**Example notification:**
> Door Sensor has reconnected 7 times in the last 60 minutes. This may indicate interference or connectivity issues.

### Daily Network Health Report

Sends a scheduled summary of your Zigbee network health.

| Input | Description | Default |
|-------|-------------|---------|
| `report_time` | Time to send the daily report | 09:00:00 |
| `low_battery_threshold` | Battery level for flagging devices | 30% |
| `offline_hours_threshold` | Hours offline to flag device | 24 |
| `notify_service` | Notification service | Empty (uses persistent notification) |
| `notification_title` | Title for the report | "ZigSight: Daily Network Health Report" |
| `include_healthy_summary` | Include count of healthy devices | true |
| `weekdays_only` | Only send on weekdays | false |

**Example report:**
```
📊 Network Health Report for 2024-01-15

**Overview:**
• Total monitored devices: 25
• Healthy devices: 23
• Devices needing attention: 2

⚠️ **Low Battery Devices (< 30%):**
• Motion Sensor Hallway
• Contact Sensor Garage

💡 Tip: Consider replacing batteries in flagged devices soon.
```

## Notification Services

The blueprints support any Home Assistant notification service. Common options:

| Service | Description |
|---------|-------------|
| `notify.mobile_app_<device>` | Push notification to mobile app |
| `notify.persistent_notification` | Home Assistant UI notification |
| `notify.telegram` | Telegram bot notification |
| `notify.pushover` | Pushover notification |
| `notify.slack` | Slack channel notification |

Leave the `notify_service` input empty to use persistent notifications (visible in the Home Assistant UI sidebar).

## Customization Tips

### Multiple Devices

Create multiple automations from the same blueprint for different devices:

```yaml
# Kitchen motion sensor
- id: battery_alert_kitchen
  use_blueprint:
    path: zigsight/battery_drain.yaml
    input:
      battery_sensor: sensor.kitchen_motion_battery
      battery_threshold: 15

# Bedroom motion sensor
- id: battery_alert_bedroom
  use_blueprint:
    path: zigsight/battery_drain.yaml
    input:
      battery_sensor: sensor.bedroom_motion_battery
      battery_threshold: 20
```

### Critical vs Non-Critical Devices

Use different thresholds and notification services for critical devices:

```yaml
# Critical: Front door lock (immediate alert)
- id: battery_critical_front_lock
  use_blueprint:
    path: zigsight/battery_drain.yaml
    input:
      battery_sensor: sensor.front_door_lock_battery
      battery_threshold: 30
      notify_service: notify.mobile_app_phone
      cooldown_hours: 12

# Non-critical: Outdoor temp sensor (weekly check)
- id: battery_outdoor_temp
  use_blueprint:
    path: zigsight/battery_drain.yaml
    input:
      battery_sensor: sensor.outdoor_temp_battery
      battery_threshold: 10
      cooldown_hours: 168
```

### Combining with Other Automations

Use blueprint automations as triggers for more complex workflows:

```yaml
automation:
  - alias: "Critical Battery - Turn on Warning Light"
    trigger:
      - platform: persistent_notification
        notification_id: zigsight_battery_*
    action:
      - service: light.turn_on
        target:
          entity_id: light.warning_indicator
        data:
          color_name: red
```

## Troubleshooting

### Blueprint Not Appearing

1. Verify the file is in the correct location (`blueprints/automation/zigsight/`)
2. Check for YAML syntax errors in the file
3. Reload automations or restart Home Assistant

### Notifications Not Sending

1. Verify your notification service is correctly configured
2. Check the notification service name matches exactly
3. Review Home Assistant logs for errors

### Too Many/Too Few Alerts

Adjust the threshold and cooldown values:
- Increase `cooldown_hours` to reduce alert frequency
- Adjust `battery_threshold` to match your preferences
- For reconnect alerts, increase `reconnect_count_threshold` or `time_window_minutes`

## See Also

- [Getting Started](getting_started.md) - ZigSight installation and setup
- [UI Documentation](ui.md) - Dashboard cards and visualization
- [Developer README](DEVELOPER_README.md) - Contributing to ZigSight
