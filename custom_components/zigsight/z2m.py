"""Zigbee2MQTT protocol parsing for ZigSight.

This module is intentionally free of Home Assistant state: it only turns raw
MQTT topics/payloads published by Zigbee2MQTT into typed Python objects, so
it can be unit tested (and reused by the fixture replay tooling) in
isolation. The coordinator owns the state and decides what to do with the
parsed data.

Reference: https://www.zigbee2mqtt.io/guide/usage/mqtt_topics_and_messages.html
"""

from __future__ import annotations

import json
import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

AVAILABILITY_SUFFIX = "availability"
BRIDGE_SEGMENT = "bridge"

# Tolerate small clock skew between Zigbee2MQTT and Home Assistant, but never
# accept a "last seen" timestamp that is clearly in the future.
_MAX_FUTURE_SKEW = timedelta(minutes=5)


class TopicKind(StrEnum):
    """Kind of a Zigbee2MQTT topic, relative to the base topic."""

    BRIDGE_DEVICES = "bridge_devices"
    BRIDGE_INFO = "bridge_info"
    BRIDGE_STATE = "bridge_state"
    BRIDGE_NETWORKMAP = "bridge_networkmap"
    BRIDGE_OTHER = "bridge_other"
    DEVICE_STATE = "device_state"
    DEVICE_AVAILABILITY = "device_availability"
    DEVICE_OTHER = "device_other"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ParsedTopic:
    """Result of classifying a topic."""

    kind: TopicKind
    friendly_name: str | None = None
    suffix: str = ""


@dataclass(slots=True)
class Z2MDevice:
    """A device as described by the retained ``<prefix>/bridge/devices``."""

    ieee_address: str
    friendly_name: str
    type: str
    network_address: int | None = None
    model: str | None = None
    vendor: str | None = None
    description: str | None = None
    model_id: str | None = None
    manufacturer: str | None = None
    power_source: str | None = None
    software_build_id: str | None = None
    interview_state: str | None = None
    disabled: bool = False
    supported: bool = True
    exposes_battery: bool = False
    exposes_voltage: bool = False
    voltage_unit: str | None = None

    @property
    def is_coordinator(self) -> bool:
        """Return True for the Zigbee coordinator itself."""
        return self.type == "Coordinator"

    @property
    def is_battery_powered(self) -> bool:
        """Return True when the device runs on battery."""
        return self.exposes_battery or (self.power_source or "").lower() == "battery"

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON serialisable representation."""
        return {
            "ieee_address": self.ieee_address,
            "friendly_name": self.friendly_name,
            "type": self.type,
            "network_address": self.network_address,
            "model": self.model,
            "vendor": self.vendor,
            "description": self.description,
            "model_id": self.model_id,
            "manufacturer": self.manufacturer,
            "power_source": self.power_source,
            "software_build_id": self.software_build_id,
            "interview_state": self.interview_state,
            "disabled": self.disabled,
            "supported": self.supported,
        }


@dataclass(slots=True)
class Z2MBridgeInfo:
    """Subset of ``<prefix>/bridge/info`` that ZigSight uses.

    Only whitelisted fields are extracted: bridge/info also contains the full
    Zigbee2MQTT configuration (MQTT credentials, network key, ...) which must
    never be stored or exposed.
    """

    version: str | None = None
    commit: str | None = None
    coordinator_ieee: str | None = None
    coordinator_type: str | None = None
    coordinator_revision: str | None = None
    channel: int | None = None
    pan_id: int | str | None = None
    extended_pan_id: int | str | None = None
    permit_join: bool | None = None
    availability_enabled: bool | None = None
    active_timeout: timedelta | None = None
    passive_timeout: timedelta | None = None
    last_seen_format: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON serialisable representation."""
        return {
            "version": self.version,
            "commit": self.commit,
            "coordinator_ieee": self.coordinator_ieee,
            "coordinator_type": self.coordinator_type,
            "coordinator_revision": self.coordinator_revision,
            "channel": self.channel,
            "pan_id": self.pan_id,
            "extended_pan_id": self.extended_pan_id,
            "permit_join": self.permit_join,
            "availability_enabled": self.availability_enabled,
            "active_timeout_minutes": (
                self.active_timeout.total_seconds() / 60
                if self.active_timeout
                else None
            ),
            "passive_timeout_minutes": (
                self.passive_timeout.total_seconds() / 60
                if self.passive_timeout
                else None
            ),
            "last_seen_format": self.last_seen_format,
        }


@dataclass(slots=True)
class NetworkLink:
    """A neighbour link from a raw network map."""

    source: str
    target: str
    lqi: int | None = None
    depth: int | None = None
    relationship: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON serialisable representation."""
        return {
            "source": self.source,
            "target": self.target,
            "lqi": self.lqi,
            "depth": self.depth,
            "relationship": self.relationship,
        }


@dataclass(slots=True)
class NetworkMap:
    """Parsed ``bridge/response/networkmap`` (type ``raw``)."""

    nodes: list[dict[str, Any]] = field(default_factory=list)
    links: list[NetworkLink] = field(default_factory=list)


def decode_payload(payload: Any) -> str:
    """Return the payload as text."""
    if isinstance(payload, bytes | bytearray):
        return bytes(payload).decode("utf-8", errors="replace")
    return str(payload)


def parse_json(payload: Any) -> Any | None:
    """Parse a JSON payload; return None (without logging an error) if invalid."""
    text = decode_payload(payload).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def classify_topic(
    topic: str, prefix: str, known_names: Collection[str]
) -> ParsedTopic:
    """Classify a topic published under the Zigbee2MQTT base topic.

    Device friendly names may contain ``/``. The device is resolved by
    looking for the *longest* known friendly name that is either the whole
    remainder of the topic or a ``/``-delimited prefix of it; whatever is
    left is the suffix (``""`` for state, ``availability``, ``set``, ...).
    Topics that don't resolve to a known device (e.g. groups) are UNKNOWN.
    """
    base = prefix.rstrip("/") + "/"
    if not topic.startswith(base):
        return ParsedTopic(TopicKind.UNKNOWN)
    rest = topic[len(base) :]
    if not rest:
        return ParsedTopic(TopicKind.UNKNOWN)

    parts = rest.split("/")
    # "bridge" is reserved by Zigbee2MQTT and can't be a device name.
    if parts[0] == BRIDGE_SEGMENT:
        sub = "/".join(parts[1:])
        if sub == "devices":
            return ParsedTopic(TopicKind.BRIDGE_DEVICES)
        if sub == "info":
            return ParsedTopic(TopicKind.BRIDGE_INFO)
        if sub == "state":
            return ParsedTopic(TopicKind.BRIDGE_STATE)
        if sub == "response/networkmap":
            return ParsedTopic(TopicKind.BRIDGE_NETWORKMAP)
        return ParsedTopic(TopicKind.BRIDGE_OTHER, suffix=sub)

    for index in range(len(parts), 0, -1):
        candidate = "/".join(parts[:index])
        if candidate in known_names:
            suffix = "/".join(parts[index:])
            if suffix == "":
                kind = TopicKind.DEVICE_STATE
            elif suffix == AVAILABILITY_SUFFIX:
                kind = TopicKind.DEVICE_AVAILABILITY
            else:
                kind = TopicKind.DEVICE_OTHER
            return ParsedTopic(kind, candidate, suffix)

    # Not (yet) a known device. Remember what the suffix would be, so the
    # caller can buffer early availability/state messages.
    if len(parts) > 1 and parts[-1] == AVAILABILITY_SUFFIX:
        return ParsedTopic(TopicKind.UNKNOWN, "/".join(parts[:-1]), AVAILABILITY_SUFFIX)
    return ParsedTopic(TopicKind.UNKNOWN, rest, "")


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _iter_exposes(exposes: Any) -> list[Mapping[str, Any]]:
    """Flatten an exposes list (including composite ``features``)."""
    result: list[Mapping[str, Any]] = []
    if not isinstance(exposes, list):
        return result
    stack = list(exposes)
    while stack:
        item = stack.pop()
        if not isinstance(item, Mapping):
            continue
        result.append(item)
        features = item.get("features")
        if isinstance(features, list):
            stack.extend(features)
    return result


def _interview_state(raw: Mapping[str, Any]) -> str | None:
    state = raw.get("interview_state")
    if isinstance(state, str) and state:
        return state.upper()
    # Zigbee2MQTT 1.x
    if raw.get("interviewing"):
        return "IN_PROGRESS"
    completed = raw.get("interview_completed")
    if completed is True:
        return "SUCCESSFUL"
    if completed is False:
        return "PENDING"
    return None


def parse_device(raw: Any) -> Z2MDevice | None:
    """Parse one entry of the bridge/devices list."""
    if not isinstance(raw, Mapping):
        return None
    ieee = _str_or_none(raw.get("ieee_address"))
    if ieee is None:
        return None
    ieee = ieee.lower()
    friendly_name = _str_or_none(raw.get("friendly_name")) or ieee
    definition = raw.get("definition")
    if not isinstance(definition, Mapping):
        definition = {}

    exposes_battery = False
    exposes_voltage = False
    voltage_unit: str | None = None
    for expose in _iter_exposes(definition.get("exposes")):
        name = expose.get("property") or expose.get("name")
        if name == "battery":
            exposes_battery = True
        elif name == "voltage":
            exposes_voltage = True
            unit = expose.get("unit")
            if isinstance(unit, str) and unit:
                voltage_unit = unit

    network_address = raw.get("network_address")
    return Z2MDevice(
        ieee_address=ieee,
        friendly_name=friendly_name,
        type=_str_or_none(raw.get("type")) or "Unknown",
        network_address=network_address if isinstance(network_address, int) else None,
        model=_str_or_none(definition.get("model")),
        vendor=_str_or_none(definition.get("vendor")),
        description=_str_or_none(definition.get("description")),
        model_id=_str_or_none(raw.get("model_id")),
        manufacturer=_str_or_none(raw.get("manufacturer")),
        power_source=_str_or_none(raw.get("power_source")),
        software_build_id=_str_or_none(raw.get("software_build_id")),
        interview_state=_interview_state(raw),
        disabled=bool(raw.get("disabled", False)),
        supported=bool(raw.get("supported", True)),
        exposes_battery=exposes_battery,
        exposes_voltage=exposes_voltage,
        voltage_unit=voltage_unit,
    )


def parse_bridge_devices(payload: Any) -> list[Z2MDevice] | None:
    """Parse ``<prefix>/bridge/devices``; None if the payload is unusable."""
    data = parse_json(payload)
    if not isinstance(data, list):
        return None
    devices: list[Z2MDevice] = []
    seen: set[str] = set()
    for raw in data:
        device = parse_device(raw)
        if device is None or device.ieee_address in seen:
            continue
        seen.add(device.ieee_address)
        devices.append(device)
    return devices


def _minutes(value: Any) -> timedelta | None:
    if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
        return timedelta(minutes=value)
    return None


def parse_bridge_info(payload: Any) -> Z2MBridgeInfo | None:
    """Parse ``<prefix>/bridge/info`` (whitelisted fields only)."""
    data = parse_json(payload)
    if not isinstance(data, Mapping):
        return None
    info = Z2MBridgeInfo(
        version=_str_or_none(data.get("version")),
        commit=_str_or_none(data.get("commit")),
    )
    permit_join = data.get("permit_join")
    if isinstance(permit_join, bool):
        info.permit_join = permit_join

    coordinator = data.get("coordinator")
    if isinstance(coordinator, Mapping):
        ieee = _str_or_none(coordinator.get("ieee_address"))
        info.coordinator_ieee = ieee.lower() if ieee else None
        info.coordinator_type = _str_or_none(coordinator.get("type"))
        meta = coordinator.get("meta")
        if isinstance(meta, Mapping):
            info.coordinator_revision = _str_or_none(meta.get("revision"))

    network = data.get("network")
    if isinstance(network, Mapping):
        channel = network.get("channel")
        if isinstance(channel, int) and not isinstance(channel, bool):
            info.channel = channel
        info.pan_id = network.get("pan_id")
        info.extended_pan_id = network.get("extended_pan_id")

    config = data.get("config")
    if isinstance(config, Mapping):
        availability = config.get("availability")
        if isinstance(availability, bool):
            info.availability_enabled = availability
        elif isinstance(availability, Mapping):
            # Zigbee2MQTT 2.x has an explicit "enabled" flag; in 1.x the
            # presence of the mapping means availability is enabled.
            enabled = availability.get("enabled", True)
            info.availability_enabled = bool(enabled)
            active = availability.get("active")
            if isinstance(active, Mapping):
                info.active_timeout = _minutes(active.get("timeout"))
            passive = availability.get("passive")
            if isinstance(passive, Mapping):
                info.passive_timeout = _minutes(passive.get("timeout"))
        advanced = config.get("advanced")
        if isinstance(advanced, Mapping):
            info.last_seen_format = _str_or_none(advanced.get("last_seen"))
    return info


def _parse_online_state(payload: Any) -> str | None:
    """Parse ``{"state": "online"}`` or the legacy plain ``online`` payload."""
    data = parse_json(payload)
    if isinstance(data, Mapping):
        state = data.get("state")
    elif isinstance(data, str):
        state = data
    else:
        state = decode_payload(payload).strip()
    if not isinstance(state, str):
        return None
    state = state.strip().lower()
    return state if state in ("online", "offline") else None


def parse_bridge_state(payload: Any) -> str | None:
    """Return ``online``/``offline`` for a bridge/state payload."""
    return _parse_online_state(payload)


def parse_availability(payload: Any) -> bool | None:
    """Return True/False for a ``<name>/availability`` payload."""
    state = _parse_online_state(payload)
    if state is None:
        return None
    return state == "online"


def parse_last_seen(value: Any, now: datetime | None = None) -> datetime | None:
    """Parse a Zigbee2MQTT ``last_seen`` value into an aware UTC datetime.

    Zigbee2MQTT publishes it as an ISO 8601 string (``ISO_8601`` in UTC or
    ``ISO_8601_local`` with an offset) or as epoch milliseconds (``epoch``),
    depending on ``advanced.last_seen``.
    """
    parsed: datetime | None = None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        try:
            parsed = dt_util.utc_from_timestamp(value / 1000)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str) and value:
        try:
            parsed = dt_util.parse_datetime(value)
        except ValueError:
            # Well formed but impossible dates (e.g. month 13)
            return None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.UTC)
    else:
        return None

    parsed = dt_util.as_utc(parsed)
    now = now or dt_util.utcnow()
    if parsed - now > _MAX_FUTURE_SKEW:
        return None
    return parsed


def _as_number(value: Any) -> float | int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return int(number) if number.is_integer() else number
    return None


# Zigbee2MQTT state keys -> ZigSight metric names
_METRIC_KEYS: dict[str, str] = {
    "linkquality": "link_quality",
    "battery": "battery",
    "voltage": "voltage",
}


def extract_metrics(payload: Mapping[str, Any]) -> dict[str, float | int]:
    """Extract the numeric metrics ZigSight tracks from a state payload.

    Only keys present (and numeric) in the payload are returned, so callers
    can merge partial updates into the previous values.
    """
    metrics: dict[str, float | int] = {}
    for key, metric in _METRIC_KEYS.items():
        if key in payload:
            number = _as_number(payload[key])
            if number is not None:
                metrics[metric] = number
    return metrics


def _link_endpoint(link: Mapping[str, Any], side: str) -> str | None:
    endpoint = link.get(side)
    ieee: Any = None
    if isinstance(endpoint, Mapping):
        ieee = endpoint.get("ieeeAddr")
    if not ieee:
        ieee = link.get(f"{side}IeeeAddr")
    return str(ieee).lower() if ieee else None


def _int_or_none(value: Any) -> int | None:
    number = _as_number(value)
    return int(number) if number is not None else None


def parse_networkmap_response(payload: Any) -> NetworkMap | None:
    """Parse a ``bridge/response/networkmap`` response of type ``raw``."""
    data = parse_json(payload)
    if not isinstance(data, Mapping):
        return None
    if data.get("status") not in (None, "ok"):
        _LOGGER.debug("Network map request failed: %s", data.get("error"))
        return None
    body = data.get("data")
    if not isinstance(body, Mapping) or body.get("type") != "raw":
        return None
    value = body.get("value")
    if not isinstance(value, Mapping):
        return None

    network_map = NetworkMap()
    for node in value.get("nodes") or []:
        if not isinstance(node, Mapping) or not node.get("ieeeAddr"):
            continue
        network_map.nodes.append(
            {
                "ieee_address": str(node["ieeeAddr"]).lower(),
                "friendly_name": node.get("friendlyName"),
                "type": node.get("type"),
                "network_address": node.get("networkAddress"),
                "failed": list(node.get("failed") or []),
            }
        )
    for link in value.get("links") or []:
        if not isinstance(link, Mapping):
            continue
        source = _link_endpoint(link, "source")
        target = _link_endpoint(link, "target")
        if not source or not target:
            continue
        lqi = link.get("lqi", link.get("linkquality"))
        network_map.links.append(
            NetworkLink(
                source=source,
                target=target,
                lqi=_int_or_none(lqi),
                depth=_int_or_none(link.get("depth")),
                relationship=_int_or_none(link.get("relationship")),
            )
        )
    return network_map
