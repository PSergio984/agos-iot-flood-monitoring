import os
import re
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)

PROC_NET_WIRELESS_PATH = "/proc/net/wireless"
DEFAULT_WIFI_INTERFACE = "wlan0"
MOCK_WIFI_RSSI = -65
FALLBACK_WIFI_RSSI = -99


def _is_mock_mode() -> bool:
    mock_env = os.getenv("MOCK_MODE", "false").strip().lower() in ("true", "1", "yes")
    return mock_env or sys.platform != "linux"


def _normalize_rssi(raw_level: float) -> int | None:
    """Convert raw driver signal level to signed dBm integer, or None if inactive."""
    # 0.0 indicates unassociated / no link
    if raw_level == 0.0:
        return None
    if raw_level > 0.0:
        raw_level = raw_level - 256.0
    rssi = int(round(raw_level))
    if rssi >= 0:
        return None
    return rssi


def parse_proc_net_wireless(content: str) -> dict[str, int]:
    """Parse /proc/net/wireless content into a mapping of active interface -> RSSI in dBm."""
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
            link_quality = float(tokens[1].rstrip("."))
            raw_level = float(tokens[2].rstrip("."))
            if link_quality == 0.0 and raw_level == 0.0:
                continue
            rssi = _normalize_rssi(raw_level)
            if rssi is not None:
                results[iface] = rssi
        except (ValueError, IndexError):
            continue
    return results


def _read_proc_wireless() -> str:
    """Read contents of /proc/net/wireless directly."""
    with open(PROC_NET_WIRELESS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _run_cmd(cmd: list[str]) -> str | None:
    """Safely execute an external CLI tool, returning stdout on success."""
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            return res.stdout
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        pass
    return None


def _query_iw_fallback(interface: str) -> int | None:
    """Fallback query using iw or iwconfig when /proc/net/wireless is unavailable."""
    attempts = [
        (["iw", "dev", interface, "link"], r"signal:\s*(-?\d+)\s*dBm"),
        (["iwconfig", interface], r"Signal level[=:]\s*(-?\d+)\s*dBm"),
    ]
    for cmd, pattern in attempts:
        out = _run_cmd(cmd)
        if out:
            match = re.search(pattern, out)
            if match:
                return int(match.group(1))
    return None


def get_wifi_signal_strength() -> int:
    """Return the Wi-Fi RSSI in dBm (e.g. -65).

    In MOCK_MODE or on non-Linux platforms, returns realistic mock RSSI (-65 dBm).
    On Linux, reads the active interface from /proc/net/wireless:
    - If WIFI_INTERFACE is configured and active in procfs, uses it.
    - Otherwise defaults to wlan0 if active, or the first active interface found.
    If unpopulated or unreadable, falls back to querying iw/iwconfig for the
    configured interface or wlan0.
    If measurement fails or interface is disconnected, safely returns -99 dBm.
    """
    if _is_mock_mode():
        return MOCK_WIFI_RSSI

    try:
        configured_iface = os.getenv("WIFI_INTERFACE", "").strip()

        try:
            content = _read_proc_wireless()
            if content:
                data = parse_proc_net_wireless(content)
                if data:
                    if configured_iface:
                        if configured_iface in data:
                            return data[configured_iface]
                    else:
                        return next(iter(data.values()))
        except (OSError, UnicodeDecodeError) as e:
            logger.debug("Failed to read %s: %s", PROC_NET_WIRELESS_PATH, e)

        # Fall back to configured WIFI_INTERFACE or DEFAULT_WIFI_INTERFACE (wlan0)
        fallback_iface = configured_iface or DEFAULT_WIFI_INTERFACE
        fallback_rssi = _query_iw_fallback(fallback_iface)
        if fallback_rssi is not None:
            return fallback_rssi

    except Exception as e:
        logger.debug("Unexpected error measuring Wi-Fi signal: %s", e)

    return FALLBACK_WIFI_RSSI
