import os
import pytest

from network import get_wifi_signal_strength


def test_get_wifi_signal_strength_in_mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    rssi = get_wifi_signal_strength()
    assert isinstance(rssi, int)
    assert rssi == -65


def test_get_wifi_signal_strength_custom_mock_rssi(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("MOCK_WIFI_RSSI", "-55")
    rssi = get_wifi_signal_strength()
    assert rssi == -55


SAMPLE_PROC_WIRELESS = """Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
 wlan0: 0000   52.  -58.  -256        0      0      0      0      0        0
"""

SAMPLE_PROC_WIRELESS_UNSIGNED = """Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
 wlan0: 0000   60.  198.  -256        0      0      0      0      0        0
"""

SAMPLE_PROC_WIRELESS_MULTI = """Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
 eth_mesh: 0000 0.   0.    0          0      0      0      0      0        0
 wlan0:    0000 55.  -62.  -256       0      0      0      0      0        0
 wlan1:    0000 40.  -75.  -256       0      0      0      0      0        0
"""


def test_parse_proc_net_wireless_standard(monkeypatch):
    from network import parse_proc_net_wireless

    result = parse_proc_net_wireless(SAMPLE_PROC_WIRELESS)
    assert result == {"wlan0": -58}


def test_parse_proc_net_wireless_unsigned_offset(monkeypatch):
    from network import parse_proc_net_wireless

    result = parse_proc_net_wireless(SAMPLE_PROC_WIRELESS_UNSIGNED)
    assert result == {"wlan0": -58}


def test_parse_proc_net_wireless_multi_interface(monkeypatch):
    from network import parse_proc_net_wireless

    result = parse_proc_net_wireless(SAMPLE_PROC_WIRELESS_MULTI)
    assert "eth_mesh" not in result
    assert result["wlan0"] == -62
    assert result["wlan1"] == -75


def test_parse_proc_net_wireless_zero_level_ignored():
    from network import parse_proc_net_wireless

    zero_content = """Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
 wlan0: 0000   0.   0.    0          0      0      0      0      0        0
"""
    assert parse_proc_net_wireless(zero_content) == {}



def test_parse_proc_net_wireless_empty_or_malformed():
    from network import parse_proc_net_wireless

    assert parse_proc_net_wireless("") == {}
    assert parse_proc_net_wireless("Invalid header\nAnother line") == {}


def test_get_wifi_signal_strength_linux_procfs_success(monkeypatch):
    import network

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setattr(network.sys, "platform", "linux")
    monkeypatch.setattr(
        network,
        "_read_proc_wireless",
        lambda: SAMPLE_PROC_WIRELESS,
    )

    rssi = network.get_wifi_signal_strength()
    assert rssi == -58


def test_get_wifi_signal_strength_specific_interface(monkeypatch):
    import network

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setattr(network.sys, "platform", "linux")
    monkeypatch.setattr(
        network,
        "_read_proc_wireless",
        lambda: SAMPLE_PROC_WIRELESS_MULTI,
    )

    assert network.get_wifi_signal_strength(interface="wlan1") == -75


def test_get_wifi_signal_strength_fallback_on_oserror(monkeypatch):
    import network

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setattr(network.sys, "platform", "linux")

    def _failing_read():
        raise OSError("Permission denied or missing file")

    monkeypatch.setattr(network, "_read_proc_wireless", _failing_read)
    monkeypatch.setattr(network, "_query_iw_fallback", lambda iface: None)

    rssi = network.get_wifi_signal_strength()
    assert rssi == -99


def test_get_wifi_signal_strength_subprocess_fallback(monkeypatch):
    import network

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setattr(network.sys, "platform", "linux")
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: "")
    monkeypatch.setattr(network, "_query_iw_fallback", lambda iface: -72)

    rssi = network.get_wifi_signal_strength()
    assert rssi == -72


def test_query_iw_fallback_iw_tool(monkeypatch):
    import network
    from subprocess import CompletedProcess

    iw_output = """Connected to 00:11:22:33:44:55 (on wlan0)
    SSID: TestWiFi
    freq: 2437
    signal: -63 dBm
    tx bitrate: 72.2 MBit/s
"""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "iw":
            return CompletedProcess(cmd, returncode=0, stdout=iw_output, stderr="")
        return CompletedProcess(cmd, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(network.subprocess, "run", fake_run)
    assert network._query_iw_fallback("wlan0") == -63


def test_query_iw_fallback_iwconfig_tool(monkeypatch):
    import network
    from subprocess import CompletedProcess

    iwconfig_output = """wlan0     IEEE 802.11  ESSID:"TestWiFi"  
          Mode:Managed  Frequency:2.437 GHz  Access Point: 00:11:22:33:44:55   
          Link Quality=55/70  Signal level=-67 dBm  
"""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "iw":
            return CompletedProcess(cmd, returncode=1, stdout="", stderr="")
        if cmd[0] == "iwconfig":
            return CompletedProcess(cmd, returncode=0, stdout=iwconfig_output, stderr="")
        return CompletedProcess(cmd, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(network.subprocess, "run", fake_run)
    assert network._query_iw_fallback("wlan0") == -67


def test_query_iw_fallback_tools_missing(monkeypatch):
    import network

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("command not found")

    monkeypatch.setattr(network.subprocess, "run", fake_run)
    assert network._query_iw_fallback("wlan0") is None


def test_auto_detection_picks_active_dongle_over_inactive_wlan0(monkeypatch):
    import network

    dongle_content = """Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
 wlan0: 0000   0.   0.    0          0      0      0      0      0        0
 wlan1: 0000   50.  -65.  -256       0      0      0      0      0        0
"""
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setattr(network.sys, "platform", "linux")
    monkeypatch.setattr(network, "_read_proc_wireless", lambda: dongle_content)

    # With no interface specified, should auto-detect the active wlan1
    rssi = network.get_wifi_signal_strength()
    assert rssi == -65


def test_query_iw_fallback_iwconfig_ignores_ratio_without_dbm(monkeypatch):
    import network
    from subprocess import CompletedProcess

    iwconfig_ratio_output = """wlan0     IEEE 802.11  ESSID:"TestWiFi"  
          Link Quality=45/70  Signal level=45/100  
"""

    def fake_run(cmd, **kwargs):
        return CompletedProcess(cmd, returncode=0, stdout=iwconfig_ratio_output, stderr="")

    monkeypatch.setattr(network.subprocess, "run", fake_run)
    assert network._query_iw_fallback("wlan0") is None




