"""Tests for the device registry helpers spanning Home Assistant versions.

Both code paths are exercised whatever Home Assistant version runs the
tests: ``PER_ENTRY_DEVICES`` (Home Assistant >= 2026.8 APIs) is patched and
the registry is a mock.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from homeassistant.helpers import device_registry as dr

from custom_components.zigsight import device_registry_compat as compat

ENTRY_ID = "entry"
IDENTIFIER = ("zigsight", "0x00158d0001a2b3c4")


@pytest.fixture
def per_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Behave like Home Assistant >= 2026.8."""
    monkeypatch.setattr(compat, "PER_ENTRY_DEVICES", True)


@pytest.fixture
def legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Behave like Home Assistant < 2026.8."""
    monkeypatch.setattr(compat, "PER_ENTRY_DEVICES", False)


def test_flag_matches_installed_home_assistant() -> None:
    """The feature flag follows the installed device registry API."""
    assert compat.PER_ENTRY_DEVICES is hasattr(
        dr.DeviceRegistry, "async_get_device_by_identifier"
    )


@pytest.mark.usefixtures("per_entry")
def test_get_entry_device_per_entry() -> None:
    """The config entry scoped lookup is used; async_get_device is not."""
    dev_reg = MagicMock()
    assert (
        compat.async_get_entry_device(dev_reg, ENTRY_ID, IDENTIFIER)
        is dev_reg.async_get_device_by_identifier.return_value
    )
    dev_reg.async_get_device_by_identifier.assert_called_once_with(IDENTIFIER, ENTRY_ID)
    dev_reg.async_get_device.assert_not_called()


@pytest.mark.usefixtures("legacy")
def test_get_entry_device_legacy() -> None:
    """Older versions look the device up by identifier."""
    dev_reg = MagicMock(spec=["async_get_device"])
    assert (
        compat.async_get_entry_device(dev_reg, ENTRY_ID, IDENTIFIER)
        is dev_reg.async_get_device.return_value
    )
    dev_reg.async_get_device.assert_called_once_with(identifiers={IDENTIFIER})


@pytest.mark.usefixtures("per_entry")
def test_remove_entry_device_per_entry() -> None:
    """A device owned by a single config entry is removed directly."""
    dev_reg = MagicMock()
    compat.async_remove_entry_device(dev_reg, SimpleNamespace(id="dev"), ENTRY_ID)  # type: ignore[arg-type]
    dev_reg.async_remove_device.assert_called_once_with("dev")
    dev_reg.async_update_device.assert_not_called()


@pytest.mark.usefixtures("legacy")
def test_remove_entry_device_legacy() -> None:
    """Older versions detach the config entry from a possibly shared device."""
    dev_reg = MagicMock()
    compat.async_remove_entry_device(dev_reg, SimpleNamespace(id="dev"), ENTRY_ID)  # type: ignore[arg-type]
    dev_reg.async_update_device.assert_called_once_with(
        "dev", remove_config_entry_id=ENTRY_ID
    )
    dev_reg.async_remove_device.assert_not_called()


@pytest.mark.usefixtures("per_entry")
def test_via_device_info_per_entry() -> None:
    """The via device is referenced by its registry id."""
    dev_reg = MagicMock()
    dev_reg.async_get_device_by_identifier.return_value = SimpleNamespace(id="bridge")
    assert compat.via_device_info(dev_reg, ENTRY_ID, IDENTIFIER) == {
        "via_device_id": "bridge"
    }

    dev_reg.async_get_device_by_identifier.return_value = None
    assert compat.via_device_info(dev_reg, ENTRY_ID, IDENTIFIER) == {}


@pytest.mark.usefixtures("legacy")
def test_via_device_info_legacy() -> None:
    """Older versions reference the via device by identifier."""
    assert compat.via_device_info(MagicMock(), ENTRY_ID, IDENTIFIER) == {
        "via_device": IDENTIFIER
    }


def test_all_devices_from_mapping_and_collection() -> None:
    """Both the old mapping and the new collection registry views work."""
    first, second = SimpleNamespace(id="a"), SimpleNamespace(id="b")
    mapping_view = MagicMock(devices={"a": first, "b": second})
    assert compat.async_all_devices(mapping_view) == [first, second]

    class _CollectionView:
        """Mimics Home Assistant 2026.9: iterable, mapping use is deprecated."""

        def __iter__(self):  # type: ignore[no-untyped-def]
            return iter([first, second])

        def values(self) -> None:
            raise AssertionError("deprecated mapping use")

    collection_view = MagicMock(devices=_CollectionView())
    assert compat.async_all_devices(collection_view) == [first, second]
