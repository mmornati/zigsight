"""Tests for Wi-Fi scanner adapters."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from custom_components.zigsight.wifi_scanner import (
    HostScanner,
    ManualScanner,
    _communicate_with_timeout,
    _filter_2_4ghz,
    _split_nmcli_terse_line,
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

    @pytest.mark.asyncio
    async def test_scan_with_invalid_type(self) -> None:
        """Test scanning with invalid type (string)."""
        scanner = ManualScanner("invalid")  # type: ignore
        result = await scanner.scan()
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

    def test_parse_nmcli_output_invalid_lines(self) -> None:
        """Test nmcli output parsing with invalid lines."""
        scanner = HostScanner()
        output = """MyNetwork:6:50
InvalidLine
AnotherNetwork:11:35"""

        result = scanner._parse_nmcli_output(output)
        # Should skip invalid lines
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_scan_no_tools_available(self) -> None:
        """Test host scanning when no tools are available."""
        scanner = HostScanner()

        # Mock both methods to return empty lists (tools not available)
        with patch.object(scanner, "_scan_with_iwlist", return_value=[]):
            with patch.object(scanner, "_scan_with_nmcli", return_value=[]):
                result = await scanner.scan()

        assert result == []

    @pytest.mark.asyncio
    async def test_scan_iwlist_success(self) -> None:
        """Test host scanning when iwlist succeeds."""
        scanner = HostScanner()

        expected_aps = [{"channel": 6, "rssi": -50, "ssid": "TestNetwork"}]

        with patch.object(scanner, "_scan_with_iwlist", return_value=expected_aps):
            result = await scanner.scan()

        assert result == expected_aps

    @pytest.mark.asyncio
    async def test_scan_iwlist_fails_nmcli_succeeds(self) -> None:
        """Test fallback to nmcli when iwlist fails."""
        scanner = HostScanner()

        expected_aps = [{"channel": 11, "rssi": -60, "ssid": "FallbackNetwork"}]

        with patch.object(
            scanner, "_scan_with_iwlist", side_effect=Exception("iwlist failed")
        ):
            with patch.object(scanner, "_scan_with_nmcli", return_value=expected_aps):
                result = await scanner.scan()

        assert result == expected_aps

    @pytest.mark.asyncio
    async def test_scan_both_fail(self) -> None:
        """Test when both scan methods fail."""
        scanner = HostScanner()

        with patch.object(
            scanner, "_scan_with_iwlist", side_effect=Exception("iwlist failed")
        ):
            with patch.object(
                scanner, "_scan_with_nmcli", side_effect=Exception("nmcli failed")
            ):
                result = await scanner.scan()

        assert result == []

    @pytest.mark.asyncio
    async def test_scan_with_iwlist_command(self) -> None:
        """Test _scan_with_iwlist handles subprocess correctly."""
        scanner = HostScanner()

        # Mock successful subprocess execution with proper async
        mock_proc = MagicMock()
        mock_proc.returncode = 0

        async def mock_communicate():
            return (
                b"""
          Cell 01 - Address: AA:BB:CC:DD:EE:FF
                    Channel:6
                    ESSID:"TestNetwork"
                    Signal level=-50 dBm
                """,
                b"",
            )

        mock_proc.communicate = mock_communicate

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await scanner._scan_with_iwlist()

        assert len(result) == 1
        assert result[0]["channel"] == 6

    @pytest.mark.asyncio
    async def test_scan_with_iwlist_command_failure(self) -> None:
        """Test _scan_with_iwlist handles command failure."""
        scanner = HostScanner()

        # Mock failed subprocess execution
        mock_proc = MagicMock()
        mock_proc.returncode = 1

        async def mock_communicate():
            return (b"", b"error")

        mock_proc.communicate = mock_communicate

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await scanner._scan_with_iwlist()

        assert result == []

    @pytest.mark.asyncio
    async def test_scan_with_iwlist_timeout(self) -> None:
        """Test _scan_with_iwlist handles timeout."""
        scanner = HostScanner()

        with patch("asyncio.create_subprocess_exec", side_effect=asyncio.TimeoutError):
            result = await scanner._scan_with_iwlist()

        assert result == []

    def test_parse_nmcli_output_escaped_colon_in_ssid(self) -> None:
        """nmcli escapes ':' in SSIDs as '\\:'; splitting on ':' would break."""
        scanner = HostScanner()
        # SSID "Office: 5G" is emitted by `nmcli -t` as "Office\: 5G".
        output = "Office\\: 5G:6:50"

        result = scanner._parse_nmcli_output(output)

        assert len(result) == 1
        assert result[0]["ssid"] == "Office: 5G"
        assert result[0]["channel"] == 6

    def test_parse_nmcli_output_escaped_backslash(self) -> None:
        """A literal backslash in a value is escaped as '\\\\' by nmcli."""
        scanner = HostScanner()
        output = "back\\\\slash:11:35"

        result = scanner._parse_nmcli_output(output)

        assert len(result) == 1
        assert result[0]["ssid"] == "back\\slash"


@pytest.mark.unit
class TestCommunicateWithTimeout:
    """Tests for the subprocess timeout/kill helper against a real process."""

    @pytest.mark.asyncio
    async def test_kills_real_process_on_timeout(self) -> None:
        """A process that outlives the timeout is killed, not left running."""
        proc = await asyncio.create_subprocess_exec(
            "sleep",
            "5",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout = await _communicate_with_timeout(proc, timeout=0.1)

        assert stdout is None
        # communicate()/wait() only return once the process has exited.
        assert proc.returncode is not None

    @pytest.mark.asyncio
    async def test_returns_stdout_when_process_finishes_in_time(self) -> None:
        """A process that finishes before the timeout returns its stdout."""
        proc = await asyncio.create_subprocess_exec(
            "echo",
            "hello",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout = await _communicate_with_timeout(proc, timeout=5)

        assert stdout is not None
        assert b"hello" in stdout


@pytest.mark.unit
class TestFilter24Ghz:
    """Tests for dropping non-2.4 GHz (Zigbee-irrelevant) access points."""

    def test_keeps_2_4ghz_channels(self) -> None:
        aps = [{"channel": 1}, {"channel": 6}, {"channel": 14}]
        assert _filter_2_4ghz(aps) == aps

    def test_drops_5ghz_channels(self) -> None:
        aps = [{"channel": 6, "ssid": "a"}, {"channel": 36, "ssid": "5ghz"}]
        assert _filter_2_4ghz(aps) == [{"channel": 6, "ssid": "a"}]

    def test_drops_missing_channel(self) -> None:
        assert _filter_2_4ghz([{"ssid": "no-channel"}]) == []


@pytest.mark.unit
class TestSplitNmcliTerseLine:
    """Tests for the escape-aware nmcli terse output splitter."""

    def test_plain_fields(self) -> None:
        assert _split_nmcli_terse_line("MyNetwork:6:50") == ["MyNetwork", "6", "50"]

    def test_escaped_colon_in_field(self) -> None:
        assert _split_nmcli_terse_line("Office\\: 5G:6:50") == [
            "Office: 5G",
            "6",
            "50",
        ]

    def test_escaped_backslash(self) -> None:
        assert _split_nmcli_terse_line("back\\\\slash:1:10") == [
            "back\\slash",
            "1",
            "10",
        ]

    def test_empty_line(self) -> None:
        assert _split_nmcli_terse_line("") == [""]


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

    def test_create_router_api_mode_rejected(self) -> None:
        """The removed router_api mode is rejected like any invalid mode."""
        with pytest.raises(ValueError, match="Invalid scanner mode"):
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
