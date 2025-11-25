# ZigSight Automation Blueprints

This folder contains Home Assistant automation blueprints for ZigSight network monitoring and alerting.

## Available Blueprints

| Blueprint | Description |
|-----------|-------------|
| [battery_drain.yaml](battery_drain.yaml) | Alert when device battery drops below threshold |
| [reconnect_flap.yaml](reconnect_flap.yaml) | Alert when device reconnects too frequently |
| [network_health_daily_report.yaml](network_health_daily_report.yaml) | Daily summary of network health |

## Quick Import

### Via Home Assistant UI (Recommended)

1. Navigate to **Settings** → **Automations & Scenes** → **Blueprints**
2. Click **Import Blueprint** in the bottom right
3. Enter the raw GitHub URL for the blueprint:
   - Battery Drain: `https://raw.githubusercontent.com/mmornati/zigsight/main/automations/battery_drain.yaml`
   - Reconnect Flap: `https://raw.githubusercontent.com/mmornati/zigsight/main/automations/reconnect_flap.yaml`
   - Daily Report: `https://raw.githubusercontent.com/mmornati/zigsight/main/automations/network_health_daily_report.yaml`
4. Click **Preview Blueprint** and then **Import Blueprint**

### Via YAML

Copy blueprint files to your Home Assistant `blueprints/automation/zigsight/` directory:

```bash
mkdir -p /config/blueprints/automation/zigsight/
cp automations/*.yaml /config/blueprints/automation/zigsight/
```

## Documentation

See [docs/automations.md](../docs/automations.md) for detailed usage instructions.
