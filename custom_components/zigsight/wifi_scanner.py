"""Wi-Fi scanner adapters for obtaining AP scan data."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Constants for RSSI conversion
RSSI_BASE_DBM = -100  # Base dBm value for percentage conversion

# Zigbee only operates in the 2.4 GHz band (channels 11-26, mapped to Wi-Fi
# channels 1-14 for interference scoring in recommender.py); a host Wi-Fi
# scan on a dual-band adapter can also report 5 GHz networks (channel
# numbers >= 36), which are irrelevant here and would otherwise pollute the
# recommendation with access points ZigSight/Zigbee can never overlap with.
WIFI_2_4GHZ_CHANNELS = range(1, 15)


def _filter_2_4ghz(aps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop access points outside the 2.4 GHz Wi-Fi channels (1-14)."""
    return [ap for ap in aps if ap.get("channel") in WIFI_2_4GHZ_CHANNELS]


async def _communicate_with_timeout(
    proc: asyncio.subprocess.Process, timeout: float
) -> bytes | None:
    """Wait for a subprocess to finish, killing it if it times out.

    ``asyncio.wait_for`` cancelling ``proc.communicate()`` does not stop the
    child process itself, which would otherwise keep running (and holding
    its pipes open) in the background. Returns stdout, or None on timeout.
    """
    try:
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        # The process may already be gone by the time we get here; killing
        # an already-dead process is a race, not a bug.
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        await proc.wait()
        return None
    return stdout


class WiFiScanner(ABC):
    """Base class for Wi-Fi scanner adapters."""

    @abstractmethod
    async def scan(self) -> list[dict[str, Any]]:
        """Perform Wi-Fi scan and return list of access points.

        Returns:
            List of dicts with keys: channel, rssi, ssid (optional)
        """


class ManualScanner(WiFiScanner):
    """Manual scanner that accepts pre-scanned data."""

    def __init__(self, scan_data: dict[str, Any] | list[dict[str, Any]]) -> None:
        """Initialize manual scanner with provided data.

        Args:
            scan_data: Either a list of APs or dict with 'access_points' key
        """
        self._scan_data = scan_data

    async def scan(self) -> list[dict[str, Any]]:
        """Return the manually provided scan data.

        Returns:
            List of access points with channel and rssi
        """
        if isinstance(self._scan_data, list):
            return self._scan_data

        # Handle dict format with 'access_points' key
        if isinstance(self._scan_data, dict):
            aps = self._scan_data.get("access_points", [])
            if isinstance(aps, list):
                return aps

        _LOGGER.warning("Invalid scan data format, returning empty list")
        return []


class HostScanner(WiFiScanner):
    """Host-based Wi-Fi scanner using system tools.

    This scanner runs Wi-Fi scanning commands on the Home Assistant host.
    Requires elevated permissions and may not work in all environments.
    """

    def __init__(self, interface: str = "wlan0") -> None:
        """Initialize host scanner.

        Args:
            interface: Wi-Fi interface name (default: wlan0)
        """
        self.interface = interface

    async def scan(self) -> list[dict[str, Any]]:
        """Perform Wi-Fi scan using host system tools.

        Returns:
            List of access points with channel and rssi
        """
        try:
            # Try iwlist first (common on Linux)
            result = await self._scan_with_iwlist()
            if result:
                return result
        except Exception as e:
            _LOGGER.debug("iwlist scan failed: %s", e)

        try:
            # Try nmcli as fallback (NetworkManager)
            result = await self._scan_with_nmcli()
            if result:
                return result
        except Exception as e:
            _LOGGER.debug("nmcli scan failed: %s", e)

        _LOGGER.warning(
            "Host Wi-Fi scanning failed. No suitable scanning tool found. "
            "This feature requires iwlist or nmcli with appropriate permissions."
        )
        return []

    async def _scan_with_iwlist(self) -> list[dict[str, Any]]:
        """Scan using iwlist command.

        Returns:
            List of access points or empty list on failure
        """
        try:
            # Run iwlist scan command
            proc = await asyncio.create_subprocess_exec(
                "iwlist",
                self.interface,
                "scan",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout = await _communicate_with_timeout(proc, timeout=30)
            if stdout is None or proc.returncode != 0:
                return []

            # Parse iwlist output; Zigbee is 2.4 GHz only, so 5 GHz results
            # (from a dual-band adapter) are dropped.
            parsed = self._parse_iwlist_output(stdout.decode("utf-8", errors="replace"))
            return _filter_2_4ghz(parsed)
        except Exception as e:
            _LOGGER.debug("iwlist execution failed: %s", e)
            return []

    def _parse_iwlist_output(self, output: str) -> list[dict[str, Any]]:
        """Parse iwlist scan output.

        Args:
            output: Raw iwlist output

        Returns:
            List of parsed access points
        """
        aps = []
        current_ap: dict[str, Any] = {}

        for line in output.splitlines():
            line = line.strip()

            # New cell/AP
            if line.startswith("Cell "):
                if current_ap:
                    aps.append(current_ap)
                current_ap = {}

            # SSID
            elif "ESSID:" in line:
                ssid = line.split("ESSID:")[1].strip().strip('"')
                if ssid:
                    current_ap["ssid"] = ssid

            # Channel
            elif "Channel:" in line:
                try:
                    channel = int(line.split("Channel:")[1].strip().split()[0])
                    current_ap["channel"] = channel
                except (ValueError, IndexError):
                    pass

            # Signal level (RSSI)
            elif "Signal level=" in line:
                try:
                    # Parse formats like "Signal level=-50 dBm" or "Signal level=60/100"
                    signal_part = line.split("Signal level=")[1].strip()
                    if "dBm" in signal_part:
                        rssi = int(signal_part.split()[0])
                    else:
                        # Convert percentage to approximate dBm
                        percent = int(signal_part.split("/")[0])
                        rssi = RSSI_BASE_DBM + percent  # Rough conversion
                    current_ap["rssi"] = rssi
                except (ValueError, IndexError):
                    pass

        # Add last AP
        if current_ap:
            aps.append(current_ap)

        # Filter APs that have both channel and rssi
        return [ap for ap in aps if "channel" in ap and "rssi" in ap]

    async def _scan_with_nmcli(self) -> list[dict[str, Any]]:
        """Scan using nmcli command (NetworkManager).

        Returns:
            List of access points or empty list on failure
        """
        try:
            # Run nmcli scan
            proc = await asyncio.create_subprocess_exec(
                "nmcli",
                "-t",
                "-f",
                "SSID,CHAN,SIGNAL",
                "dev",
                "wifi",
                "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout = await _communicate_with_timeout(proc, timeout=30)
            if stdout is None or proc.returncode != 0:
                return []

            # Parse nmcli output; Zigbee is 2.4 GHz only, so 5 GHz results
            # (from a dual-band adapter) are dropped.
            parsed = self._parse_nmcli_output(stdout.decode("utf-8", errors="replace"))
            return _filter_2_4ghz(parsed)
        except Exception as e:
            _LOGGER.debug("nmcli execution failed: %s", e)
            return []

    def _parse_nmcli_output(self, output: str) -> list[dict[str, Any]]:
        """Parse nmcli -t (terse) output.

        Args:
            output: Raw nmcli terse output, ':' separated

        Returns:
            List of parsed access points
        """
        aps = []

        for line in output.splitlines():
            parts = _split_nmcli_terse_line(line)
            if len(parts) >= 3:
                ssid = parts[0].strip()
                try:
                    channel = int(parts[1].strip())
                    signal = int(parts[2].strip())
                    # nmcli gives signal as percentage, convert to approximate dBm
                    rssi = RSSI_BASE_DBM + signal

                    ap: dict[str, Any] = {"channel": channel, "rssi": rssi}
                    if ssid:
                        ap["ssid"] = ssid

                    aps.append(ap)
                except (ValueError, IndexError):
                    continue

        return aps


def _split_nmcli_terse_line(line: str) -> list[str]:
    """Split a line of ``nmcli -t`` terse output on unescaped ':'.

    nmcli escapes literal ':' and '\\' inside field values with a leading
    backslash (e.g. an SSID containing ':' is emitted as ``foo\\:bar``); a
    plain ``line.split(":")`` would wrongly cut such SSIDs into extra
    fields. This walks the line respecting those escapes and unescapes each
    field.
    """
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def create_scanner(
    mode: str,
    scan_data: dict[str, Any] | list[dict[str, Any]] | None = None,
    host_config: dict[str, Any] | None = None,
) -> WiFiScanner:
    """Factory function to create appropriate scanner.

    Args:
        mode: Scanner mode (manual, host_scan)
        scan_data: Data for manual mode
        host_config: Configuration for host_scan mode

    Returns:
        WiFiScanner instance

    Raises:
        ValueError: If mode is invalid or required config is missing
    """
    mode = mode.lower()

    if mode == "manual":
        if scan_data is None:
            raise ValueError("scan_data is required for manual mode")
        return ManualScanner(scan_data)

    if mode == "host_scan":
        interface = "wlan0"
        if host_config:
            interface = host_config.get("interface", "wlan0")
        return HostScanner(interface=interface)

    raise ValueError(f"Invalid scanner mode: {mode}")
