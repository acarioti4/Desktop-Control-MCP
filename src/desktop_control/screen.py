"""Screenshot capture and DPI awareness initialization.

IMPORTANT: This module MUST be imported before pyautogui to ensure
DPI awareness is set correctly on Windows.
"""

import ctypes
import io

# DPI awareness MUST be set before importing pyautogui or PIL
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import mss
from PIL import Image


def capture_screenshot(
    monitor_index: int = 1,
    region: dict | None = None,
    quality: int = 60,
) -> tuple[bytes, int, int, dict | None]:
    """Capture a screenshot and return (jpeg_bytes, screen_width, screen_height, region_info).

    Args:
        monitor_index: 1 = primary monitor (default), 2 = secondary, 0 = all combined.
        region: Optional dict with {left, top, width, height} to capture a sub-area.
        quality: JPEG quality (1-100). Default 60 balances size and clarity.

    Returns:
        Tuple of (jpeg_bytes, screen_width, screen_height, region_info).
        region_info is None for full screenshots, or the region dict for sub-area captures.
    """
    with mss.mss() as sct:
        # Always resolve the actual screen dimensions from the primary monitor
        primary = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        screen_w = primary["width"]
        screen_h = primary["height"]

        if region:
            grab_target = region
        elif monitor_index < len(sct.monitors):
            grab_target = sct.monitors[monitor_index]
        else:
            grab_target = primary

        screenshot = sct.grab(grab_target)
        img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        jpeg_bytes = buf.getvalue()

        return jpeg_bytes, screen_w, screen_h, region if region else None


def get_monitors() -> list[dict]:
    """Return list of monitor geometries."""
    with mss.mss() as sct:
        return [
            {
                "index": i,
                "left": m["left"],
                "top": m["top"],
                "width": m["width"],
                "height": m["height"],
            }
            for i, m in enumerate(sct.monitors)
        ]


def get_cursor_position() -> tuple[int, int]:
    """Return current cursor (x, y) position."""
    import pyautogui
    return pyautogui.position()


def get_scaling_factor() -> float:
    """Return the DPI scaling factor for the primary monitor."""
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return dpi / 96.0
    except Exception:
        return 1.0
