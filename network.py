import os
import re
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)

PROC_NET_WIRELESS_PATH = "/proc/net/wireless"
DEFAULT_WIFI_INTERFACE = "wlan0"
MOCK_WIFI_RSSI_DEFAULT = -65
FALLBACK_WIFI_RSSI = -99


def _is_mock_mode() -> bool:
    mock_env = os.getenv("MOCK_MODE", "false").strip().lower() in ("true", "1", "yes")
    return mock_env or sys.platform != "linux"


def _get_mock_wifi_signal_strength() -> int:
    try:
        return int(os.getenv("MOCK_WIFI_RSSI", str(MOCK_WIFI_RSSI_DEFAULT)))
    except (ValueError, TypeError):
        return MOCK_WIFI_RSSI_DEFAULT


def parse_proc_net_wireless(content: str) -> dict[str, int]:
    """Parse /proc/net/wireless content into a mapping of interface -> RSSI in dBm."""
    results: dict[str, int] = {}
    lines = content.splitlines()
    for line in lines:
        if ":" not in line:
            continue
        parts = line.split(":", 1)
        iface = parts[0].strip()
        tokens = parts[1].split()
        if len(tokens) < 3:
            continue
        try:
            # tokens[0] is status, tokens[1] is link quality, tokens[2] is level (dBm)
            raw_level_str = tokens[2].rstrip(".")
            raw_level = float(raw_level_str)
            if raw_level > 0:
                raw_level = raw_level - 256.0
            results[iface] = int(round(raw_level))
        except (ValueError, IndexError):
            continue
    return results


def _read_proc_wireless() -> str:
    """Read contents of /proc/net/wireless directly."""
    with open(PROC_NET_WIRELESS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _query_iw_fallback(interface: str) -> int | None:
    """Fallback query using iw or iwconfig when /proc/net/wireless is unavailable."""
    # 1. Try: iw dev <interface> link
    try:
        res = subprocess.run(
            ["iw", "dev", interface, "link"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            match = re.search(r"signal:\s*(-?\d+)\s*dBm", res.stdout)
            if match:
                return int(match.group(1))
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        pass

    # 2. Try: iwconfig <interface>
    try:
        res = subprocess.run(
            ["iwconfig", interface],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            match = re.search(r"Signal level[=:]\s*(-?\d+)\s*dBm", res.stdout)
            if match:
                return int(match.group(1))
            # Some drivers output "Signal level=X/Y" or "Signal level=X"
            match = re.search(r"Signal level[=:]\s*(-?\d+)", res.stdout)
            if match:
                val = int(match.group(1))
                if val > 0:
                    val = val - 256
                return val
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        pass

    return None


def get_wifi_signal_strength(interface: str | None = None) -> int:
    """Return the Wi-Fi RSSI in dBm (e.g. -65).

    In MOCK_MODE or on non-Linux platforms, returns a mock RSSI (default -65 dBm).
    On Linux, reads from /proc/net/wireless or fallback tools.
    If measurement fails or interface is disconnected, safely returns -99 dBm.
    """
    if _is_mock_mode():
        return _get_mock_wifi_signal_strength()

    target_iface = (interface or os.getenv("WIFI_INTERFACE", "")).strip()

    try:
        content = _read_proc_wireless()
        if content:
            data = parse_proc_net_wireless(content)
            if data:
                if target_iface and target_iface in data:
                    return data[target_iface]
                if not target_iface:
                    if DEFAULT_WIFI_INTERFACE in data:
                        return data[DEFAULT_WIFI_INTERFACE]
                    return next(iter(data.values()))
    except (OSError, UnicodeDecodeError) as e:
        logger.debug("Failed to read %s: %s", PROC_NET_WIRELESS_PATH, e)

    # Attempt fallback using iw/iwconfig if procfs read did not yield a value
    fallback_iface = target_iface or DEFAULT_WIFI_INTERFACE
    fallback_rssi = _query_iw_fallback(fallback_iface)
    if fallback_rssi is not None:
        return fallback_rssi

    return FALLBACK_WIFI_RSSI
