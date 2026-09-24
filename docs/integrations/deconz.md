# deCONZ Integration

> **Coming Soon**: deCONZ support is planned for a future release. Currently, ZigSight supports Zigbee2MQTT and ZHA integrations.

## Overview

[deCONZ](https://phoscon.de/en/conbee/) is Dresden Elektronik's software for their ConBee and RaspBee Zigbee gateways. Future versions of ZigSight will integrate with deCONZ to collect device data and compute analytics.

## Current Status

deCONZ integration is not yet available in ZigSight. If you're using deCONZ, you can:

1. **Use Zigbee2MQTT instead**: Many users migrate from deCONZ to Zigbee2MQTT for better features and compatibility
2. **Wait for deCONZ support**: Follow the [GitHub repository](https://github.com/mmornati/zigsight) for updates on deCONZ support

## Planned Features

When deCONZ support is added, it will include:

- Automatic device discovery from deCONZ
- Device health monitoring and analytics
- Wi-Fi channel recommendations
- Network topology visualization
- Integration with Home Assistant's deCONZ integration

## Configuration (Planned)

### Step 1: Obtain API Key

If you don't have an API key:

1. Open the Phoscon web interface (usually `http://your-ip:8080/pwa`)
2. Go to **Settings** > **Gateway** > **Advanced**
3. Click **Authenticate app**
4. In the Phoscon App, go to **Settings** > **API key** and note the key

Alternatively, generate via API:

```bash
# Unlock gateway first (press button in Phoscon or call unlock endpoint)
curl -X POST http://your-ip:8080/api -d '{"devicetype":"zigsight"}'
```

### Step 2: Add ZigSight Integration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "ZigSight"
4. Select **deCONZ** as the integration type

### Step 3: Configure deCONZ Connection

Enter the following details:

| Field | Description | Example |
|-------|-------------|---------|
| Host | deCONZ hostname or IP | `192.168.1.100` or `core-deconz` |
| Port | deCONZ API port | `8080` (default) |
| API Key | Your deCONZ API key | `ABCDEF1234567890` |

### Step 4: Configure Analytics (Optional)

Customize the analytics thresholds:

| Setting | Description | Default |
|---------|-------------|---------|
| Battery Drain Threshold | Minimum drain rate (%/hour) to trigger warning | 10.0 |
| Reconnect Rate Threshold | Maximum reconnect rate (events/hour) before warning | 5.0 |
| Reconnect Rate Window | Time window in hours for calculations | 24 |

## How It Works

### Device Discovery

ZigSight queries the deCONZ REST API for device information:

```
GET /api/{api_key}/lights
GET /api/{api_key}/sensors
GET /api/{api_key}/config
```

It also connects to the websocket for real-time updates:

```
ws://host:port/ws
```

### Data Collected

For each device, ZigSight collects:

- **Device Name**: Name from deCONZ
- **Device Type**: Based on device classification
- **Unique ID**: MAC address/unique identifier
- **Link Quality (LQI)**: Signal strength when available
- **Battery Level**: Current battery percentage
- **Last Seen**: Timestamp of last update
- **Manufacturer**: Device manufacturer
- **Model ID**: Device model identifier
- **Reachable**: Current reachability status

### API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `/api/{key}/config` | Gateway configuration and network info |
| `/api/{key}/lights` | Light devices and their states |
| `/api/{key}/sensors` | Sensor devices and their states |
| `/api/{key}/groups` | Group information |
| Websocket | Real-time state updates |

## Entities Created

ZigSight creates sensors for each Zigbee device:

### Sensors

- `sensor.{device}_health_score` - Overall health (0-100)
- `sensor.{device}_reconnect_rate` - Reconnection frequency (events/hour)
- `sensor.{device}_battery_trend` - Battery drain rate (%/hour)

### Binary Sensors

- `binary_sensor.{device}_connectivity_warning` - Connectivity issue alert
- `binary_sensor.{device}_battery_drain_warning` - Battery drain alert

## Channel Recommendation

deCONZ allows channel changes through its interface. To optimize your channel:

1. Run the ZigSight Wi-Fi scan service to get a recommendation
2. Open the deCONZ GUI application
3. Go to **Settings** > **Gateway**
4. Change the channel to the recommended value
5. Restart deCONZ and wait for devices to rejoin

See [Wi-Fi Recommendation](../wifi_recommendation.md) for detailed instructions.

## Troubleshooting

### Connection Errors

```
Cannot connect to deCONZ at host:port
```

Solutions:

- Verify deCONZ is running
- Check host and port configuration
- Ensure the API key is valid
- Check firewall settings

### API Key Invalid

```
Unauthorized: Invalid API key
```

Solutions:

- Regenerate the API key in Phoscon
- Ensure the gateway was unlocked when creating the key
- Check for extra spaces in the key

### Devices Not Appearing

1. **Check deCONZ interface**: Verify devices are visible in Phoscon
2. **Verify API access**: Test the API endpoint directly
3. **Check device types**: ZigSight processes lights and sensors
4. **Review logs**: Enable debug logging for details

### Missing Link Quality

Not all devices report LQI. This is normal for:

- The gateway itself
- Some older devices
- Devices that use simplified reporting

### Websocket Disconnections

If real-time updates aren't working:

1. Check if port 443 is blocked (websocket port)
2. Verify network connectivity
3. Restart the ZigSight integration
4. Check deCONZ logs for websocket errors

## Best Practices

### API Key Security

- Use a dedicated API key for ZigSight
- Don't share API keys between applications
- Regenerate if you suspect compromise

### deCONZ Maintenance

- Keep deCONZ firmware updated
- Backup your deCONZ configuration regularly
- Monitor the deCONZ logs for issues

### Network Optimization

- Position the ConBee/RaspBee centrally
- Add routers (mains-powered devices) for coverage
- Use the Wi-Fi recommendation service to avoid interference

## deCONZ-Specific Features

### Network Map

deCONZ provides a network map in the desktop application:

1. Open deCONZ GUI (not Phoscon)
2. Select **View** > **Network**
3. See device connections and routes

This complements ZigSight's topology card.

### Device Firmware Updates

Some devices support OTA updates through deCONZ:

1. Open Phoscon web interface
2. Go to device settings
3. Check for available firmware updates

Updated firmware can improve device reliability.

## Using with Home Assistant Add-on

If running deCONZ as a Home Assistant add-on:

- Host: `core-deconz`
- Port: `40850` (usually)
- Websocket port: `8443`

Check the add-on configuration for exact ports.

## Related Documentation

- [deCONZ Official Documentation](https://dresden-elektronik.github.io/deconz-rest-doc/)
- [Phoscon App Documentation](https://phoscon.de/en/support/)
- [ZigSight Analytics](../analytics.md)
- [ZigSight Wi-Fi Recommendation](../wifi_recommendation.md)
- [ZigSight Automations](../automations.md)
