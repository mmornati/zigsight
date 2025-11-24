"""Wi-Fi scanner adapters for obtaining AP scan data."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Constants for RSSI conversion
RSSI_BASE_DBM = -100  # Base dBm value for percentage conversion


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


class RouterAPIScanner(WiFiScanner):
    """Router API scanner for querying router endpoints.

    Supports UniFi, OpenWrt, Fritz!Box and other router APIs.
    """

    def __init__(
        self,
        router_type: str,
        host: str,
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize router API scanner.

        Args:
            router_type: Type of router (unifi, openwrt, fritzbox)
            host: Router hostname or IP address
            username: Router admin username (if needed)
            password: Router admin password (if needed)
            api_key: API key for authentication (if supported)
        """
        self.router_type = router_type.lower()
        self.host = host
        self.username = username
        self.password = password
        self.api_key = api_key

    async def scan(self) -> list[dict[str, Any]]:
        """Query router API for Wi-Fi scan data.

        Returns:
            List of access points with channel and rssi
        """
        # This is a placeholder for actual router API implementations
        # In production, this would make HTTP requests to router APIs
        _LOGGER.info(
            "Router API scan not yet implemented for %s at %s",
            self.router_type,
            self.host,
        )
        _LOGGER.info(
            "Router API scanning requires router-specific implementation. "
            "For now, use manual mode with exported scan data from your router."
        )
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

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode != 0:
                return []

            # Parse iwlist output
            return self._parse_iwlist_output(stdout.decode("utf-8"))
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

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode != 0:
                return []

            # Parse nmcli output
            return self._parse_nmcli_output(stdout.decode("utf-8"))
        except Exception as e:
            _LOGGER.debug("nmcli execution failed: %s", e)
            return []

    def _parse_nmcli_output(self, output: str) -> list[dict[str, Any]]:
        """Parse nmcli output.

        Args:
            output: Raw nmcli output (tab-separated)

        Returns:
            List of parsed access points
        """
        aps = []

        for line in output.splitlines():
            parts = line.split(":")
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


def create_scanner(
    mode: str,
    scan_data: dict[str, Any] | list[dict[str, Any]] | None = None,
    router_config: dict[str, Any] | None = None,
    host_config: dict[str, Any] | None = None,
) -> WiFiScanner:
    """Factory function to create appropriate scanner.

    Args:
        mode: Scanner mode (manual, router_api, host_scan)
        scan_data: Data for manual mode
        router_config: Configuration for router_api mode
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

    if mode == "router_api":
        if router_config is None:
            raise ValueError("router_config is required for router_api mode")
        return RouterAPIScanner(
            router_type=router_config.get("router_type", ""),
            host=router_config.get("host", ""),
            username=router_config.get("username"),
            password=router_config.get("password"),
            api_key=router_config.get("api_key"),
        )

    if mode == "host_scan":
        interface = "wlan0"
        if host_config:
            interface = host_config.get("interface", "wlan0")
        return HostScanner(interface=interface)

    raise ValueError(f"Invalid scanner mode: {mode}")
