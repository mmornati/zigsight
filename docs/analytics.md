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
**Unit**: events/hour  
**Description**: Measures how often a device reconnects to the network over a sliding time window.

**Default Window**: 24 hours  
**Calculation**: Counts reconnection events (gaps > 5 minutes between updates) within the window and divides by window duration.

**Example**:
- A device that reconnects 12 times in 24 hours = 0.5 events/hour
- A device that reconnects 240 times in 24 hours = 10 events/hour (high, indicates connectivity issues)

### Battery Trend

**Sensor**: `sensor.<device>_battery_trend`  
**Unit**: %/hour  
**Description**: Rate of battery drain computed using linear regression over the last 24 hours.

**Algorithm**: 
- Extracts battery readings from device history
- Filters readings with battery ≥ 20% (below threshold, readings may be unreliable)
- Computes linear regression slope to determine trend
- Returns percentage change per hour (negative = draining)

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
- **Battery** (20%): Current battery level (0-100%)
- **Reconnect Rate** (30%): Inverted reconnect rate (lower is better)
- **Connectivity** (20%): Based on last_seen recency (< 5 min = 100, > 1 hour = 0)

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
**Device Class**: `connectivity`  
**Description**: Triggers when connectivity issues are detected.

**Default Threshold**: 5 events/hour  
**Configuration**: Set via `reconnect_rate_threshold` in integration options

**When It Triggers**:
- Reconnect rate ≥ 5 events/hour (default)
- OR device hasn't been seen for > 1 hour

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

- **Maximum History**: 1000 entries per device (last entries kept)
- **Retention Period**: Configurable via `retention_days` (default: 30 days)
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

