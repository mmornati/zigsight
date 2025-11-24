"""Tests for Wi-Fi scanner adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.zigsight.wifi_scanner import (
    HostScanner,
    ManualScanner,
    RouterAPIScanner,
    create_scanner,
)


@pytest.mark.unit
class TestManualScanner:
    """Tests for ManualScanner."""

    @pytest.mark.asyncio
    async def test_scan_with_list(self) -> None:
        """Test scanning with list input."""
        scan_data = [
            {"channel": 1, "rssi": -50},
            {"channel": 6, "rssi": -60},
        ]
        scanner = ManualScanner(scan_data)
        result = await scanner.scan()

        assert result == scan_data

    @pytest.mark.asyncio
    async def test_scan_with_dict(self) -> None:
        """Test scanning with dict input."""
        aps = [
            {"channel": 1, "rssi": -50},
            {"channel": 6, "rssi": -60},
        ]
        scan_data = {"access_points": aps}
        scanner = ManualScanner(scan_data)
        result = await scanner.scan()

        assert result == aps

    @pytest.mark.asyncio
    async def test_scan_with_invalid_data(self) -> None:
        """Test scanning with invalid data."""
        scanner = ManualScanner({"invalid": "data"})
        result = await scanner.scan()

        assert result == []

    @pytest.mark.asyncio
    async def test_scan_with_empty_list(self) -> None:
        """Test scanning with empty list."""
        scanner = ManualScanner([])
        result = await scanner.scan()

        assert result == []


@pytest.mark.unit
class TestRouterAPIScanner:
    """Tests for RouterAPIScanner."""

    @pytest.mark.asyncio
    async def test_router_api_scanner_init(self) -> None:
        """Test router API scanner initialization."""
        scanner = RouterAPIScanner(
            router_type="unifi",
            host="192.168.1.1",
            username="admin",
            password="password",
        )

        assert scanner.router_type == "unifi"
        assert scanner.host == "192.168.1.1"
        assert scanner.username == "admin"

    @pytest.mark.asyncio
    async def test_router_api_scanner_not_implemented(self) -> None:
        """Test that router API scanning returns empty list (not yet implemented)."""
        scanner = RouterAPIScanner(
            router_type="unifi",
            host="192.168.1.1",
        )
        result = await scanner.scan()

        # Should return empty list as implementation is placeholder
        assert result == []


@pytest.mark.unit
class TestHostScanner:
    """Tests for HostScanner."""

    @pytest.mark.asyncio
    async def test_host_scanner_init(self) -> None:
        """Test host scanner initialization."""
        scanner = HostScanner(interface="wlan1")
        assert scanner.interface == "wlan1"

    @pytest.mark.asyncio
    async def test_host_scanner_default_interface(self) -> None:
        """Test host scanner with default interface."""
        scanner = HostScanner()
        assert scanner.interface == "wlan0"

    def test_parse_iwlist_output(self) -> None:
        """Test iwlist output parsing."""
        scanner = HostScanner()
        output = """
          Cell 01 - Address: AA:BB:CC:DD:EE:FF
                    Channel:6
                    ESSID:"MyNetwork"
                    Signal level=-50 dBm
          Cell 02 - Address: 11:22:33:44:55:66
                    Channel:11
                    ESSID:"AnotherNetwork"
                    Signal level=-65 dBm
        """

        result = scanner._parse_iwlist_output(output)

        assert len(result) == 2
        assert result[0]["channel"] == 6
        assert result[0]["rssi"] == -50
        assert result[0]["ssid"] == "MyNetwork"
        assert result[1]["channel"] == 11
        assert result[1]["rssi"] == -65

    def test_parse_iwlist_output_empty(self) -> None:
        """Test iwlist output parsing with empty output."""
        scanner = HostScanner()
        result = scanner._parse_iwlist_output("")
        assert result == []

    def test_parse_iwlist_output_incomplete(self) -> None:
        """Test iwlist output parsing with incomplete data."""
        scanner = HostScanner()
        output = """
          Cell 01 - Address: AA:BB:CC:DD:EE:FF
                    ESSID:"MyNetwork"
        """

        # Should not include APs without both channel and rssi
        result = scanner._parse_iwlist_output(output)
        assert result == []

    def test_parse_nmcli_output(self) -> None:
        """Test nmcli output parsing."""
        scanner = HostScanner()
        output = """MyNetwork:6:50
AnotherNetwork:11:35
HiddenNetwork:1:70"""

        result = scanner._parse_nmcli_output(output)

        assert len(result) == 3
        assert result[0]["channel"] == 6
        assert result[0]["rssi"] == -50  # 50% -> -50 dBm
        assert result[0]["ssid"] == "MyNetwork"

    def test_parse_nmcli_output_empty(self) -> None:
        """Test nmcli output parsing with empty output."""
        scanner = HostScanner()
        result = scanner._parse_nmcli_output("")
        assert result == []

    @pytest.mark.asyncio
    async def test_scan_no_tools_available(self) -> None:
        """Test host scanning when no tools are available."""
        scanner = HostScanner()

        # Mock both methods to return empty lists (tools not available)
        with patch.object(scanner, "_scan_with_iwlist", return_value=[]):
            with patch.object(scanner, "_scan_with_nmcli", return_value=[]):
                result = await scanner.scan()

        assert result == []


@pytest.mark.unit
class TestCreateScanner:
    """Tests for scanner factory function."""

    def test_create_manual_scanner(self) -> None:
        """Test creating manual scanner."""
        scan_data = [{"channel": 1, "rssi": -50}]
        scanner = create_scanner(mode="manual", scan_data=scan_data)

        assert isinstance(scanner, ManualScanner)

    def test_create_manual_scanner_no_data(self) -> None:
        """Test creating manual scanner without data."""
        with pytest.raises(ValueError, match="scan_data is required"):
            create_scanner(mode="manual")

    def test_create_router_api_scanner(self) -> None:
        """Test creating router API scanner."""
        router_config = {
            "router_type": "unifi",
            "host": "192.168.1.1",
            "username": "admin",
        }
        scanner = create_scanner(mode="router_api", router_config=router_config)

        assert isinstance(scanner, RouterAPIScanner)
        assert scanner.router_type == "unifi"

    def test_create_router_api_scanner_no_config(self) -> None:
        """Test creating router API scanner without config."""
        with pytest.raises(ValueError, match="router_config is required"):
            create_scanner(mode="router_api")

    def test_create_host_scanner(self) -> None:
        """Test creating host scanner."""
        scanner = create_scanner(mode="host_scan")

        assert isinstance(scanner, HostScanner)
        assert scanner.interface == "wlan0"

    def test_create_host_scanner_with_config(self) -> None:
        """Test creating host scanner with custom config."""
        host_config = {"interface": "wlan1"}
        scanner = create_scanner(mode="host_scan", host_config=host_config)

        assert isinstance(scanner, HostScanner)
        assert scanner.interface == "wlan1"

    def test_create_scanner_invalid_mode(self) -> None:
        """Test creating scanner with invalid mode."""
        with pytest.raises(ValueError, match="Invalid scanner mode"):
            create_scanner(mode="invalid_mode")

    def test_create_scanner_case_insensitive(self) -> None:
        """Test that scanner mode is case-insensitive."""
        scan_data = [{"channel": 1, "rssi": -50}]
        scanner = create_scanner(mode="MANUAL", scan_data=scan_data)

        assert isinstance(scanner, ManualScanner)
