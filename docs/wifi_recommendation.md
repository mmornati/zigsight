# Wi-Fi Interference Analysis and Zigbee Channel Recommendation

This guide explains how to use ZigSight's Wi-Fi interference analysis to optimize your Zigbee network by selecting the best channel.

## Overview

Zigbee and Wi-Fi both operate in the 2.4 GHz spectrum, which can lead to interference and degraded performance. ZigSight analyzes Wi-Fi access points in your environment and recommends the optimal Zigbee channel (11, 15, 20, or 25) to minimize interference.

## Understanding Channel Overlap

### Wi-Fi Channels
Wi-Fi channels in the 2.4 GHz band use approximately 22 MHz of bandwidth each. While common channels are 1, 6, and 11, any channels from 1-13 (or 1-14 in some regions) may be in use.

### Zigbee Channels
Zigbee uses much narrower channels (~2 MHz) numbered 11-26 in the 2.4 GHz band. However, only channels **11, 15, 20, and 25** are recommended because they provide optimal spacing from common Wi-Fi channels.

### Overlap Mapping
- **Zigbee Channel 11** (~2405 MHz): Overlaps with Wi-Fi channels 1-2
- **Zigbee Channel 15** (~2425 MHz): Overlaps with Wi-Fi channels 2-4
- **Zigbee Channel 20** (~2450 MHz): Overlaps with Wi-Fi channels 6-8
- **Zigbee Channel 25** (~2475 MHz): Overlaps with Wi-Fi channels 11-13

## Using the Service

### Method 1: Manual Upload (Recommended for Most Users)

This is the easiest method. Export Wi-Fi scan data from your router, then upload it to ZigSight.

#### Step 1: Obtain Wi-Fi Scan Data

See the router-specific guides below for how to export Wi-Fi scan data.

#### Step 2: Call the Service

1. In Home Assistant, go to **Developer Tools** > **Services**
2. Select service: `zigsight.recommend_channel`
3. Set mode to `manual`
4. Paste your Wi-Fi scan data in the `wifi_scan_data` field

Example service call:
```yaml
service: zigsight.recommend_channel
data:
  mode: manual
  wifi_scan_data:
    - channel: 1
      rssi: -45
      ssid: "MyNetwork"
    - channel: 6
      rssi: -60
      ssid: "NeighborNetwork"
    - channel: 11
      rssi: -75
      ssid: "AnotherNetwork"
```

The service will log the recommendation and explanation to Home Assistant logs. You can also retrieve the last recommendation from `hass.data[DOMAIN]["last_recommendation"]`.

### Method 2: Router API Mode

This mode directly queries your router's API for Wi-Fi scan data (when implemented for your router).

**Note:** Router API support is currently a placeholder and requires router-specific implementation. For now, use manual mode.

Example (future functionality):
```yaml
service: zigsight.recommend_channel
data:
  mode: router_api
  router_type: unifi
  host: 192.168.1.1
  username: admin
  password: your_password
```

### Method 3: Host Scan Mode

This mode runs a Wi-Fi scan directly on your Home Assistant host using system tools (iwlist or nmcli).

**Requirements:**
- Home Assistant running on hardware with a Wi-Fi adapter
- Appropriate permissions to run scanning commands
- May require a privileged add-on configuration

Example:
```yaml
service: zigsight.recommend_channel
data:
  mode: host_scan
  interface: wlan0  # Optional, defaults to wlan0
```

**Note:** This mode may not work in Docker containers or supervised installations without additional configuration.

## Router-Specific Guides

### UniFi

1. Log in to your UniFi controller
2. Navigate to **Insights** > **Wi-Fi**
3. View the **RF Environment** scan
4. Export or note down:
   - Channel numbers
   - RSSI values (signal strength)
   - SSIDs

Format for ZigSight:
```json
[
  {"channel": 1, "rssi": -45, "ssid": "Network1"},
  {"channel": 6, "rssi": -60, "ssid": "Network2"}
]
```

### OpenWrt

1. SSH into your OpenWrt router
2. Run: `iwinfo wlan0 scan`
3. Note the Channel and Signal values
4. Format as JSON for ZigSight

### Fritz!Box

1. Log in to Fritz!Box web interface
2. Navigate to **WLAN** > **Radio Channel**
3. View the channel usage graph
4. Note which channels have active networks
5. Estimate RSSI based on signal strength indicators

### Generic Router

Most routers have a Wi-Fi analyzer or channel scanner:
1. Look for "Wi-Fi Analyzer", "Channel Scanner", or "RF Environment" in your router settings
2. Export or screenshot the scan results
3. Create a JSON list with channel and approximate RSSI values

**RSSI Guidelines:**
- Excellent signal: -30 to -50 dBm
- Good signal: -50 to -65 dBm
- Fair signal: -65 to -80 dBm
- Weak signal: -80 to -90 dBm

## Understanding Results

The service returns:
- **recommended_channel**: The best Zigbee channel (11, 15, 20, or 25)
- **scores**: Interference scores for all 4 channels (0 = best, 100 = worst)
- **explanation**: Human-readable summary of the analysis

Example result logged:
```
INFO: Zigbee channel recommendation: Channel 15 (score: 12.3)
INFO: Recommendation: Analyzed 8 Wi-Fi access points on channels: Ch1 (3 APs), Ch6 (2 APs), Ch11 (3 APs). 
      Zigbee channel 15 has the lowest interference score (12.3/100). 
      This channel has minimal Wi-Fi interference.
```

## Changing Your Zigbee Channel

**⚠️ IMPORTANT: Changing your Zigbee channel requires careful planning**

### Before You Change

1. **Backup your Zigbee network configuration** through your coordinator software (Zigbee2MQTT, ZHA, or deCONZ)
2. **Plan for downtime**: All devices will temporarily disconnect
3. **Ensure all devices are powered**: Battery devices should have fresh batteries
4. **Schedule the change**: Pick a time when automation disruption is acceptable

### Migration Checklist

- [ ] Run Wi-Fi scan and get channel recommendation
- [ ] Backup Zigbee coordinator configuration
- [ ] Verify all devices are online and responsive
- [ ] Schedule migration during low-activity period
- [ ] Change coordinator channel in your Zigbee software
- [ ] Restart coordinator
- [ ] Wait 10-15 minutes for devices to rejoin
- [ ] Verify all devices are back online
- [ ] Test automations

### Zigbee2MQTT

1. Stop Zigbee2MQTT
2. Edit `configuration.yaml`:
   ```yaml
   advanced:
     channel: 15  # Your recommended channel
   ```
3. Start Zigbee2MQTT
4. Devices will automatically rejoin (may take 10-15 minutes)

### ZHA (Home Assistant)

1. Go to **Settings** > **Devices & Services** > **Zigbee Home Automation**
2. Click **Configure**
3. Select **Change channel**
4. Enter your recommended channel
5. Confirm and wait for migration to complete

### deCONZ

1. Open deCONZ GUI
2. Go to **Settings** > **Gateway**
3. Change the channel number
4. Restart deCONZ
5. Devices will rejoin automatically

## Troubleshooting

### No Recommendation Available
- Ensure Wi-Fi scan data is properly formatted
- Check Home Assistant logs for error messages
- Verify JSON syntax if using manual mode

### Devices Not Rejoining After Channel Change
- Wait at least 15-20 minutes for battery devices
- Power cycle mains-powered devices (routers help extend the network)
- Check coordinator logs for rejoin attempts
- If needed, re-pair devices starting with routers first

### High Interference Scores on All Channels
- This indicates a very busy 2.4 GHz spectrum
- Consider moving Wi-Fi networks to 5 GHz if possible
- Use the channel with the lowest score even if it's not ideal
- Monitor Zigbee network performance and adjust if needed

### Host Scan Not Working
- Verify Wi-Fi adapter is available: `iwconfig` or `ip link`
- Check permissions: May need to run as root or with capabilities
- Try both iwlist and nmcli methods
- Consider using manual mode as alternative

## Best Practices

1. **Run scans periodically**: Wi-Fi networks change over time
2. **Scan during peak hours**: Get a realistic picture of interference
3. **Consider all neighbors**: Include all visible networks, not just yours
4. **Don't change channels frequently**: Zigbee networks need time to stabilize
5. **Document your changes**: Keep notes on channel changes and results

## Additional Resources

- [Zigbee2MQTT: Best Practices](https://www.zigbee2mqtt.io/guide/usage/best_practices.html)
- [ZHA Channel Migration Guide](https://www.home-assistant.io/integrations/zha/)
- [Understanding 2.4 GHz Spectrum](https://www.metageek.com/training/resources/zigbee-wifi-coexistence/)

## Support

If you encounter issues:
1. Check Home Assistant logs for error messages
2. Verify Wi-Fi scan data format
3. Open an issue on GitHub with:
   - Home Assistant version
   - ZigSight version
   - Wi-Fi scan data (redact SSIDs if needed)
   - Error messages from logs
