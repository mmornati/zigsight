# ZigSight Analytics

ZigSight provides powerful analytics capabilities to monitor and diagnose Zigbee device health and connectivity issues.

## Overview

The analytics engine processes device metrics over time to compute derived insights:

- **Reconnect Rate**: Frequency of device reconnections per hour
- **Battery Trend**: Rate of battery drain (percentage per hour)
- **Health Score**: Aggregated health metric (0-100) combining multiple factors
- **Battery Drain Warning**: Binary alert when battery drain exceeds threshold
- **Connectivity Warning**: Binary alert when connectivity issues are detected

## Metrics

### Reconnect Rate

**Sensor**: `sensor.<device>_reconnect_rate`
**Unit**: events/h
**Description**: Measures how often a device reconnects to the network over a sliding time window.

**Default Window**: 24 hours
**Calculation**: Counts reconnect events within the window and divides by the window duration. A reconnect event is an availability transition **offline -> online** as published by Zigbee2MQTT on `<base_topic>/<device>/availability`. A device that simply stays quiet (for example a sleepy battery sensor reporting once an hour) is *not* counted as reconnecting.

> **Note**: reconnects can only be detected when [availability](https://www.zigbee2mqtt.io/guide/configuration/device-availability.html) is enabled in Zigbee2MQTT. Without it the reconnect rate stays at 0. Reconnect events are kept in memory only (at most 200 per device) and restart from zero when Home Assistant restarts.

**Example**:
- A device that reconnects 12 times in 24 hours = 0.5 events/hour
- A device that reconnects 240 times in 24 hours = 10 events/hour (high, indicates connectivity issues)

### Battery Trend

**Sensor**: `sensor.<device>_battery_trend`
**Unit**: %/hour
**Description**: Rate of battery drain computed using linear regression over the last 24 hours.

**Algorithm**:
- Extracts battery readings from the in-memory device history (a numeric sample is stored at most every 5 minutes, or after 1 minute when the battery value changed; at most 400 samples per device)
- Uses every reading, including low batteries (below 20%)
- Requires readings spanning at least 1 hour (otherwise `None`), so two readings a few seconds apart can't extrapolate to a huge drain
- Computes the linear regression slope and returns the percentage change per hour (negative = draining)

Battery sensors, battery trend and the battery drain warning are only created for battery powered devices.

**Example**:
- `-0.5` = Battery draining at 0.5% per hour
- `-2.0` = Battery draining at 2% per hour (concerning for low battery devices)
- `None` = Insufficient data to compute trend

### Health Score

**Sensor**: `sensor.<device>_health_score`
**Unit**: None (0-100 scale)
**Description**: Aggregated health metric combining multiple device factors.

**Components** (default weights):
- **Link Quality** (30%): Normalized signal strength (0-255 → 0-100)
- **Battery** (20%): Current battery level (0-100%). Left out (and the other weights re-normalised) for mains powered devices
- **Reconnect Rate** (30%): Inverted reconnect rate (lower is better)
- **Connectivity** (20%): 100 when Zigbee2MQTT reports the device online, 0 when offline. Without availability information it decays linearly from 100 (just seen) to 0 when the device has been silent for the [silent device timeout](#connectivity-warning) (25 hours)

**Score Interpretation**:
- **90-100**: Excellent health
- **70-89**: Good health
- **50-69**: Fair health (monitor closely)
- **0-49**: Poor health (investigate issues)

**Example**:
```
Device with:
- Link Quality: 200/255 → 78.4 score
- Battery: 80%
- Reconnect Rate: 0.5/hour → 95 score
- Connectivity: Seen 2 min ago → 100 score

Health Score = (78.4 × 0.3) + (80 × 0.2) + (95 × 0.3) + (100 × 0.2) = 86.6
```

## Warnings

### Battery Drain Warning

**Binary Sensor**: `binary_sensor.<device>_battery_drain_warning`
**Device Class**: `problem`
**Description**: Triggers when battery drain rate exceeds configured threshold.

**Default Threshold**: 10%/hour
**Configuration**: Set via `battery_drain_threshold` in integration options

**When It Triggers**:
- Battery trend < -10%/hour (default)
- Example: Device battery dropped from 80% to 50% in 3 hours = -10%/hour

**Troubleshooting**:
- Check device placement (poor signal increases power usage)
- Verify battery is not defective
- Review device logs for transmission errors
- Consider replacing battery if drain persists

### Connectivity Warning

**Binary Sensor**: `binary_sensor.<device>_connectivity_warning`
**Device Class**: `problem` ("on" = there is a connectivity problem)
**Description**: Triggers when connectivity issues are detected.

**Default Threshold**: 5 events/hour
**Configuration**: Set via `reconnect_rate_threshold` in integration options

**When It Triggers**:
- Reconnect rate ≥ 5 events/hour (default)
- OR Zigbee2MQTT reports the device **offline** (availability enabled)
- OR, when Zigbee2MQTT availability is not tracking the device (it is disabled by default in Zigbee2MQTT 2.x), the device hasn't been seen for longer than the **silent device timeout: 25 hours**, for every device type

Zigbee2MQTT uses a short 10 minute timeout for routers only because it actively pings them; ZigSight doesn't ping devices, and idle routers (bulbs, plugs) can legitimately stay silent for hours, so a short router timeout would only produce false warnings. The 25 hours mirror Zigbee2MQTT's "passive" availability default; when Zigbee2MQTT publishes its own `availability.passive.timeout` in `bridge/info`, that value is used. Enable availability in Zigbee2MQTT for timely offline detection: when it tracks a device, its online/offline state is used directly.

When Zigbee2MQTT itself is offline (`bridge/state`), every device's availability is unknown and availability messages are ignored (retained ones are stale, e.g. when Home Assistant starts while Zigbee2MQTT is stopped): the stale state doesn't raise warnings, and the "online" published after Zigbee2MQTT restarts is not counted as a reconnect.

The entity has two attributes: `available` (Zigbee2MQTT availability, `null` when unknown) and `reconnect_count` (reconnects since Home Assistant started).

**Troubleshooting**:
- Check device distance from coordinator
- Verify Zigbee channel interference
- Review link quality metrics
- Check for physical obstructions
- Verify device firmware is up to date

## Configuration

### Threshold Configuration

All thresholds are configurable during integration setup or via options flow:

- **Battery Drain Threshold**: Minimum drain rate (%/hour) to trigger warning (default: 10.0)
- **Reconnect Rate Threshold**: Maximum reconnect rate (events/hour) before warning (default: 5.0)
- **Reconnect Rate Window**: Time window in hours for reconnect rate calculation (default: 24)

### Tuning Thresholds

**For Stable Networks**:
- Reduce `reconnect_rate_threshold` to 2-3 events/hour
- Reduce `battery_drain_threshold` to 5-7%/hour for better early detection

**For Noisy Networks**:
- Increase `reconnect_rate_threshold` to 10+ events/hour
- Increase `battery_drain_threshold` to 15+/hour to avoid false positives

**For Battery-Optimized Monitoring**:
- Use longer `reconnect_rate_window_hours` (48-72) for better averaging
- Adjust `battery_drain_threshold` based on device type (motion sensors drain faster than door sensors)

## Worked Examples

### Example 1: Detecting Battery Issues

**Scenario**: Door sensor battery drains quickly after installation.

**Setup**:
```
battery_drain_threshold: 8.0  # More sensitive
```

**Monitoring**:
1. Check `sensor.door_sensor_battery_trend` → Shows `-2.5 %/hour`
2. Check `binary_sensor.door_sensor_battery_drain_warning` → `ON`
3. Check `sensor.door_sensor_battery` → Shows 45%

**Action**: Battery is draining at 2.5%/hour, triggering warning. Check device placement and signal quality.

### Example 2: Identifying Connectivity Problems

**Scenario**: Motion sensor frequently disconnects and reconnects.

**Setup**:
```
reconnect_rate_threshold: 5.0
reconnect_rate_window_hours: 24
```

**Monitoring**:
1. Check `sensor.motion_sensor_reconnect_rate` → Shows `12.5 events/hour`
2. Check `binary_sensor.motion_sensor_connectivity_warning` → `ON`
3. Check `sensor.motion_sensor_health_score` → Shows `35` (poor)

**Action**: High reconnect rate (12.5/hour) indicates connectivity issues. Check signal strength and device placement.

### Example 3: Health Score Trend Analysis

**Scenario**: Monitoring overall device health over time.

**Setup**:
- Track `sensor.<device>_health_score` in Home Assistant history
- Create automations based on score thresholds

**Monitoring**:
- Device starts at 85 (good)
- Over 1 week, score drops to 60 (fair)
- Check individual components:
  - Link quality: Stable at 75
  - Battery: Dropped from 90% to 65%
  - Reconnect rate: Increased from 0.2 to 2.0/hour

**Action**: Battery and connectivity are degrading. Investigate root causes.

## Troubleshooting

### Metrics Show "Unknown"

**Cause**: Insufficient historical data.

**Solution**:
- Wait for more device updates (analytics needs at least 2-3 data points)
- Verify MQTT connection is working
- Check device is sending regular updates

### Health Score Seems Inaccurate

**Cause**: Default weights may not fit your use case.

**Solution**:
- Review individual component scores (link quality, battery, reconnect rate, connectivity)
- Consider your network priorities (battery life vs. connectivity)
- Note: Weights are currently fixed in code but may be configurable in future versions

### Warnings Trigger Too Frequently

**Cause**: Thresholds too sensitive for your environment.

**Solution**:
- Increase thresholds via integration options
- Review device logs to understand normal behavior
- Adjust based on device type (motion sensors behave differently than door sensors)

### Battery Trend Not Available

**Cause**: Battery readings below minimum threshold or insufficient data.

**Solution**:
- Ensure device reports battery level
- Wait for more historical data points
- Check if battery is below 20% (trend calculation minimum)

## Data Retention

Analytics calculations use device history stored in memory:

- **Maximum History**: 1000 entries per device (last entries kept, in-memory only, not persisted across restarts)
- **Memory Usage**: Approximately 10-50 KB per device depending on history size

For persistent storage and long-term analysis, use Home Assistant's built-in history features to record sensor values.

## Future Enhancements

Potential future improvements:

- Configurable health score weights
- Additional metrics (route stability, router load)
- Predictive battery life estimation
- Anomaly detection for unusual patterns
- Historical trend visualization
- Integration with Home Assistant automations for proactive alerts
