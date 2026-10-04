import os
import pytest
from subprocess import CompletedProcess

import network
from network import get_wifi_signal_strength, parse_proc_net_wireless


PROC_HEADER = (
    "Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE\n"
    " face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22\n"
)


def make_proc_content(*lines: str) -> str:
    """Helper to construct synthetic /proc/net/wireless content without repeated headers."""
    return PROC_HEADER + "".join(f"{line}\n" for line in lines)


@pytest.fixture
def linux_mode(monkeypatch):
    """Fixture to simulate a Linux environment with mock mode disabled."""
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setattr(network.sys, "platform", "linux")


def test_get_wifi_signal_strength_in_mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    rssi = get_wifi_signal_strength()
    assert isinstance(rssi, int)
    assert rssi == -65


def test_get_wifi_signal_strength_non_linux_platform(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setattr(network.sys, "platform", "win32")
    assert get_wifi_signal_strength() == -65


def test_parse_proc_net_wireless_standard():
    content = make_proc_content(" wlan0: 0000   52.  -58.  -256        0      0      0      0      0        0")
    assert parse_proc_net_wireless(content) == {"wlan0": -58}


def test_parse_proc_net_wireless_unsigned_offset():
    content = make_proc_content(" wlan0: 0000   60.  198.  -256        0      0      0      0      0        0")
    assert parse_proc_net_wireless(content) == {"wlan0": -58}


def test_parse_proc_net_wireless_multi_interface():
    content = make_proc_content(
        " eth_mesh: 0000 0.   0.    0          0      0      0      0      0        0",
        " wlan0:    0000 55.  -62.  -256       0      0      0      0      0        0",
        " wlan1:    0000 40.  -75.  -256       0      0      0      0      0        0",
    )
    result = parse_proc_net_wireless(content)
    assert "eth_mesh" not in result
    assert result["wlan0"] == -62
    assert result["wlan1"] == -75


def test_parse_proc_net_wireless_zero_level_ignored():
    content = make_proc_content(" wlan0: 0000   0.   0.    0          0      0      0      0      0        0")
    assert parse_proc_net_wireless(content) == {}


def test_parse_proc_net_wireless_empty_or_malformed():
    assert parse_proc_net_wireless("") == {}
    assert parse_proc_net_wireless("Invalid header\nAnother line") == {}


def test_get_wifi_signal_strength_linux_procfs_success(linux_mode, monkeypatch):
    content = make_proc_content(" wlan0: 0000   52.  -58.  -256        0      0      0      0      0        0")
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: content)
    assert get_wifi_signal_strength() == -58


def test_auto_detection_picks_first_interface_in_procfs(linux_mode, monkeypatch):
    content = make_proc_content(
        " wlan1: 0000   50.  -65.  -256       0      0      0      0      0        0",
        " wlan0: 0000   40.  -78.  -256       0      0      0      0      0        0",
    )
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: content)
    assert get_wifi_signal_strength() == -65


def test_get_wifi_signal_strength_honors_wifi_interface_in_procfs(linux_mode, monkeypatch):
    content = make_proc_content(
        " wlan0: 0000   40.  -78.  -256       0      0      0      0      0        0",
        " wlan1: 0000   50.  -65.  -256       0      0      0      0      0        0",
    )
    monkeypatch.setenv("WIFI_INTERFACE", "wlan1")
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: content)
    assert get_wifi_signal_strength() == -65


def test_get_wifi_signal_strength_configured_interface_not_in_procfs_falls_back_to_cli(linux_mode, monkeypatch):
    content = make_proc_content(" wlan0: 0000   52.  -58.  -256        0      0      0      0      0        0")
    monkeypatch.setenv("WIFI_INTERFACE", "wlan1")
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: content)
    queried = []
    monkeypatch.setattr(network, "_query_iw_fallback", lambda iface: queried.append(iface) or -73)
    assert get_wifi_signal_strength() == -73
    assert queried == ["wlan1"]


def test_auto_detection_picks_active_dongle_when_wlan0_inactive(linux_mode, monkeypatch):
    content = make_proc_content(
        " wlan0: 0000   0.   0.    0          0      0      0      0      0        0",
        " wlan1: 0000   50.  -65.  -256       0      0      0      0      0        0",
    )
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: content)
    assert get_wifi_signal_strength() == -65


def test_get_wifi_signal_strength_disconnected_returns_negative_99(linux_mode, monkeypatch):
    content = make_proc_content(" wlan0: 0000   0.   0.    0          0      0      0      0      0        0")
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: content)
    monkeypatch.setattr(network, "_query_iw_fallback", lambda iface: None)
    assert get_wifi_signal_strength() == -99


def test_get_wifi_signal_strength_fallback_on_oserror(linux_mode, monkeypatch):
    def _failing_read():
        raise OSError("Permission denied or missing file")

    monkeypatch.setattr(network, "_read_proc_wireless", _failing_read)
    monkeypatch.setattr(network, "_query_iw_fallback", lambda iface: None)
    assert get_wifi_signal_strength() == -99


def test_get_wifi_signal_strength_handles_unexpected_exception(linux_mode, monkeypatch):
    def _exploding_read():
        raise RuntimeError("Unexpected kernel crash simulation")

    monkeypatch.setattr(network, "_read_proc_wireless", _exploding_read)
    assert get_wifi_signal_strength() == -99


def test_get_wifi_signal_strength_subprocess_fallback(linux_mode, monkeypatch):
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: "")
    monkeypatch.setattr(network, "_query_iw_fallback", lambda iface: -72)
    assert get_wifi_signal_strength() == -72


def test_get_wifi_signal_strength_uses_wifi_interface_env_for_fallback(linux_mode, monkeypatch):
    queried_ifaces = []
    monkeypatch.setenv("WIFI_INTERFACE", "wlan_custom")
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: "")
    monkeypatch.setattr(
        network,
        "_query_iw_fallback",
        lambda iface: queried_ifaces.append(iface) or -70,
    )
    assert get_wifi_signal_strength() == -70
    assert queried_ifaces == ["wlan_custom"]


def _fake_command_runner(success_tool: str, stdout_text: str):
    def fake_run(cmd, **kwargs):
        if cmd[0] == success_tool:
            return CompletedProcess(cmd, returncode=0, stdout=stdout_text, stderr="")
        return CompletedProcess(cmd, returncode=1, stdout="", stderr="")

    return fake_run


def test_query_iw_fallback_iw_tool(monkeypatch):
    iw_output = (
        "Connected to 00:11:22:33:44:55 (on wlan0)\n"
        "    SSID: TestWiFi\n"
        "    freq: 2437\n"
        "    signal: -63 dBm\n"
        "    tx bitrate: 72.2 MBit/s\n"
    )
    monkeypatch.setattr(network.subprocess, "run", _fake_command_runner("iw", iw_output))
    assert network._query_iw_fallback("wlan0") == -63


def test_query_iw_fallback_iwconfig_tool(monkeypatch):
    iwconfig_output = (
        "wlan0     IEEE 802.11  ESSID:\"TestWiFi\"\n"
        "          Mode:Managed  Frequency:2.437 GHz  Access Point: 00:11:22:33:44:55\n"
        "          Link Quality=55/70  Signal level=-67 dBm\n"
    )
    monkeypatch.setattr(network.subprocess, "run", _fake_command_runner("iwconfig", iwconfig_output))
    assert network._query_iw_fallback("wlan0") == -67


def test_query_iw_fallback_tools_missing(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("command not found")

    monkeypatch.setattr(network.subprocess, "run", fake_run)
    assert network._query_iw_fallback("wlan0") is None


def test_query_iw_fallback_iwconfig_ignores_ratio_without_dbm(monkeypatch):
    iwconfig_ratio_output = (
        "wlan0     IEEE 802.11  ESSID:\"TestWiFi\"\n"
        "          Link Quality=45/70  Signal level=45/100\n"
    )
    monkeypatch.setattr(network.subprocess, "run", _fake_command_runner("iwconfig", iwconfig_ratio_output))
    assert network._query_iw_fallback("wlan0") is None
