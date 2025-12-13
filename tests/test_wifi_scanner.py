"""Tests for Wi-Fi scanner adapters."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.zigsight.wifi_scanner import (
    HostScanner,
    ManualScanner,
    RouterAPIScanner,
    create_scanner,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manual_scanner_basic() -> None:
    """Test manual scanner with list input."""
    scan_data = [
        {"channel": 1, "rssi": -50},
        {"channel": 6, "rssi": -60},
    ]
    scanner = ManualScanner(scan_data)
    result = await scanner.scan()

    assert result == scan_data


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manual_scanner_with_dict() -> None:
    """Test manual scanner with dict input."""
    aps = [
        {"channel": 1, "rssi": -50},
        {"channel": 6, "rssi": -60},
    ]
    scan_data = {"access_points": aps}
    scanner = ManualScanner(scan_data)
    result = await scanner.scan()

    assert result == aps


@pytest.mark.unit
@pytest.mark.asyncio
async def test_router_api_scanner_not_implemented() -> None:
    """Test that router API scanning returns empty list (not yet implemented)."""
    scanner = RouterAPIScanner(
        router_type="unifi",
        host="192.168.1.1",
    )
    result = await scanner.scan()

    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_host_scanner_no_tools() -> None:
    """Test host scanning when no tools are available."""
    scanner = HostScanner()

    with patch.object(scanner, "_scan_with_iwlist", return_value=[]):
        with patch.object(scanner, "_scan_with_nmcli", return_value=[]):
            result = await scanner.scan()

    assert result == []


@pytest.mark.unit
def test_create_manual_scanner() -> None:
    """Test creating manual scanner."""
    scan_data = [{"channel": 1, "rssi": -50}]
    scanner = create_scanner(mode="manual", scan_data=scan_data)

    assert isinstance(scanner, ManualScanner)


@pytest.mark.unit
def test_create_router_api_scanner() -> None:
    """Test creating router API scanner."""
    router_config = {
        "router_type": "unifi",
        "host": "192.168.1.1",
        "username": "admin",
    }
    scanner = create_scanner(mode="router_api", router_config=router_config)

    assert isinstance(scanner, RouterAPIScanner)
    assert scanner.router_type == "unifi"


@pytest.mark.unit
def test_create_host_scanner() -> None:
    """Test creating host scanner."""
    scanner = create_scanner(mode="host_scan")

    assert isinstance(scanner, HostScanner)
    assert scanner.interface == "wlan0"


@pytest.mark.unit
def test_create_scanner_invalid_mode() -> None:
    """Test creating scanner with invalid mode."""
    with pytest.raises(ValueError, match="Invalid scanner mode"):
        create_scanner(mode="invalid_mode")
