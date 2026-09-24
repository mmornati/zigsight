"""Tests for scripts/ci_check_ha_log.py (the e2e Home Assistant log gate)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ci_check_ha_log.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ci_check_ha_log", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ci_check_ha_log"] = module
    spec.loader.exec_module(module)
    return module


checker = _load()

TS = "2026-09-24 10:00:00.123"

MQTT_CALLBACK_EXCEPTION = f"""\
{TS} INFO (MainThread) [homeassistant.setup] Setting up zigsight
{TS} ERROR (MainThread) [homeassistant.components.mqtt.client] Exception in _async_handle_message when handling msg on 'zigbee2mqtt/Kitchen': '{{"linkquality": 12}}'
Traceback (most recent call last):
  File "/usr/src/homeassistant/homeassistant/components/mqtt/client.py", line 1000, in _async_handle_callback_exception
    msg_callback(msg)
  File "/config/custom_components/zigsight/coordinator.py", line 325, in _async_handle_message
    self._handle_device_state(
KeyError: 'Kitchen'
{TS} INFO (MainThread) [homeassistant.core] Something unrelated
"""

ERROR_ADDING_ENTITY = (
    f"{TS} ERROR (MainThread) [homeassistant.helpers.entity_platform] Error adding "
    "entity sensor.kitchen_link_quality for domain sensor with platform zigsight\n"
)

BLOCKING_CALL = (
    f"{TS} WARNING (MainThread) [homeassistant.util.loop] Detected blocking call "
    "to open with args ('/config/x',) inside the event loop by custom integration "
    "'zigsight' at custom_components/zigsight/api.py, line 12\n"
)

WARNING_TRACEBACK_ONLY = f"""\
{TS} WARNING (MainThread) [homeassistant.core] Something went sideways
Traceback (most recent call last):
  File "/config/custom_components/zigsight/topology.py", line 10, in build
    raise ValueError("boom")
ValueError: boom
"""

CLEAN_LOG = f"""\
{TS} WARNING (SyncWorker_0) [homeassistant.loader] We found a custom integration zigsight which has not been tested by Home Assistant. This component might cause stability problems, be sure to disable it if you experience issues with Home Assistant
{TS} INFO (MainThread) [homeassistant.setup] Setup of domain zigsight took 0.12 seconds
{TS} ERROR (MainThread) [homeassistant.components.tts] Unrelated error from another integration
Traceback (most recent call last):
  File "/usr/src/homeassistant/homeassistant/components/tts/__init__.py", line 1, in x
RuntimeError: nope
"""


def test_mqtt_callback_exception_with_traceback_path_is_detected() -> None:
    problems = checker.find_problems(MQTT_CALLBACK_EXCEPTION)
    assert len(problems) == 1
    assert "Exception in _async_handle_message" in problems[0]
    assert "custom_components/zigsight/coordinator.py" in problems[0]


def test_error_adding_entity_is_detected() -> None:
    problems = checker.find_problems(ERROR_ADDING_ENTITY)
    assert len(problems) == 1
    assert "ERROR record" in problems[0]


def test_blocking_call_warning_is_detected() -> None:
    problems = checker.find_problems(BLOCKING_CALL)
    assert len(problems) == 1
    assert "Detected" in problems[0]


def test_warning_with_zigsight_traceback_is_detected() -> None:
    problems = checker.find_problems(WARNING_TRACEBACK_ONLY)
    assert len(problems) == 1
    assert "traceback" in problems[0]


@pytest.mark.parametrize(
    "line",
    [
        f"{TS} ERROR (MainThread) [custom_components.zigsight.coordinator] boom",
        f"{TS} CRITICAL (MainThread) [custom_components.ZigSight] boom",
        f"{TS} ERROR (MainThread) [homeassistant.setup] Setup failed for custom integration 'zigsight'",
    ],
)
def test_error_and_critical_lines_mentioning_zigsight(line: str) -> None:
    assert len(checker.find_problems(line + "\n")) == 1


def test_ansi_coloured_log_is_parsed() -> None:
    coloured = "\x1b[31m" + MQTT_CALLBACK_EXCEPTION.replace(
        "\n", "\x1b[0m\n\x1b[31m", 2
    )
    problems = checker.find_problems(coloured)
    assert len(problems) == 1
    assert "\x1b" not in problems[0]
    records = checker.split_records("\x1b[33m" + TS + " WARNING (x) [y] z\x1b[0m\n")
    assert records[0].level == "WARNING"


def test_clean_log_passes() -> None:
    assert checker.find_problems(CLEAN_LOG) == []


def test_long_record_is_truncated_in_report() -> None:
    frames = "\n".join(
        f'  File "/config/custom_components/zigsight/x.py", line {i}, in f'
        for i in range(50)
    )
    text = (
        f"{TS} ERROR (MainThread) [x] oops\nTraceback (most recent call last):\n"
        f"{frames}\nValueError: x\n"
    )
    (problem,) = checker.find_problems(text)
    assert "more lines" in problem


def test_lines_before_first_timestamp_form_their_own_record() -> None:
    records = checker.split_records("s6-rc: info: service legacy-services started\n")
    assert len(records) == 1
    assert records[0].level is None


def test_main_fails_on_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert checker.main(["x", str(tmp_path / "missing.log")]) == 1
    assert "missing or empty" in capsys.readouterr().out


def test_main_fails_on_empty_file(tmp_path: Path) -> None:
    log = tmp_path / "ha.log"
    log.write_text("   \n", encoding="utf-8")
    assert checker.main(["x", str(log)]) == 1


def test_main_fails_on_problem_and_passes_on_clean(tmp_path: Path) -> None:
    bad = tmp_path / "bad.log"
    bad.write_text(MQTT_CALLBACK_EXCEPTION, encoding="utf-8")
    good = tmp_path / "good.log"
    good.write_text(CLEAN_LOG, encoding="utf-8")
    assert checker.main(["x", str(bad)]) == 1
    assert checker.main(["x", str(good)]) == 0


def test_main_usage_error() -> None:
    assert checker.main(["x"]) == 2
