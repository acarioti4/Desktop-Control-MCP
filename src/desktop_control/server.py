"""Desktop Control MCP Server.

Gives LLMs eyes (screenshots + element detection) and hands (mouse/keyboard)
on a Windows desktop. Uses a three-layer detection strategy:
- CDP for Electron apps (Discord, VS Code, Slack)
- UIA for native Windows apps (Notepad, Explorer, Settings)
- Vision (screenshots) as fallback for everything else
"""

import json
import time

from mcp.server.fastmcp import FastMCP, Image

# Import screen FIRST to initialize DPI awareness before pyautogui
from desktop_control.screen import (
    capture_screenshot,
    get_cursor_position,
    get_monitors,
    get_scaling_factor,
)
from desktop_control.mouse import click, drag, scroll
from desktop_control.keyboard import type_text, hotkey, press_key
from desktop_control.windows import open_app, list_windows
from desktop_control import element_detection

mcp = FastMCP("Desktop Control")


# ── Vision & Awareness Tools ──────────────────────────────────────────


@mcp.tool()
async def screenshot(
    monitor_index: int = 1,
    region: dict | None = None,
    quality: int = 60,
) -> list:
    """Capture a screenshot of the desktop.

    Returns the image and screen dimensions. Use this to see what's on screen
    before deciding where to click.

    Args:
        monitor_index: 1 = primary monitor (default), 2 = secondary, 0 = all combined.
        region: Optional {left, top, width, height} to capture a sub-area.
            When using a region, pixel (0,0) in the image = (left, top) on screen.
        quality: JPEG quality (1-100). Default 60 balances size and clarity.
    """
    try:
        jpeg_bytes, screen_w, screen_h, region_info = capture_screenshot(
            monitor_index, region, quality
        )
        if region_info:
            info = (
                f"Region screenshot captured. "
                f"Screen dimensions: {screen_w}x{screen_h}. "
                f"This image shows region: left={region_info['left']}, top={region_info['top']}, "
                f"width={region_info['width']}, height={region_info['height']}. "
                f"To click something at pixel (px, py) in THIS image, use "
                f"mouse_click(x={region_info['left']}+px, y={region_info['top']}+py)."
            )
        else:
            info = (
                f"Screenshot captured. Screen dimensions: {screen_w}x{screen_h}. "
                f"Coordinates in this image map 1:1 to mouse coordinates."
            )
        return [info, Image(data=jpeg_bytes, format="jpeg")]
    except Exception as e:
        return [f"ERROR: Screenshot failed - {e}"]


@mcp.tool()
async def get_elements(
    window_title: str,
    element_type: str | None = None,
    name_filter: str | None = None,
    max_depth: int = 8,
) -> str:
    """Get interactive UI elements from a window with exact bounding boxes.

    Auto-detects whether the app is Electron (uses CDP) or native (uses UIA).
    Returns element names, types, and screen coordinates for precise clicking.

    Args:
        window_title: Window title or substring to search for.
        element_type: Filter by type (e.g. "Button", "button", "ListItem").
        name_filter: Filter by name/text substring.
        max_depth: Max depth for UIA tree traversal (default 8).
    """
    try:
        elements = await element_detection.get_elements(
            window_title=window_title,
            element_type=element_type,
            name_filter=name_filter,
            max_depth=max_depth,
        )
        if not elements:
            return f"No elements found in window '{window_title}'."

        return json.dumps(elements, indent=2)
    except Exception as e:
        return f"ERROR: Element detection failed - {e}"


@mcp.tool()
async def get_screen_info() -> str:
    """Get screen information: monitors, cursor position, DPI scale.

    Useful for understanding the coordinate space before taking actions.
    """
    try:
        monitors = get_monitors()
        cursor = get_cursor_position()
        scale = get_scaling_factor()
        return json.dumps({
            "monitors": monitors,
            "cursor": {"x": cursor[0], "y": cursor[1]},
            "dpi_scale": scale,
        }, indent=2)
    except Exception as e:
        return f"ERROR: {e}"


# ── Mouse Tools ───────────────────────────────────────────────────────


@mcp.tool()
async def mouse_click(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
    hold_keys: list[str] | None = None,
) -> str:
    """Click at screen coordinates.

    Args:
        x: X coordinate (pixels from left edge).
        y: Y coordinate (pixels from top edge).
        button: "left", "right", or "middle".
        clicks: Number of clicks (2 for double-click).
        hold_keys: Modifier keys to hold (e.g. ["ctrl"], ["shift"]).
    """
    try:
        return click(x, y, button, clicks, hold_keys)
    except Exception as e:
        return f"ERROR: Click failed - {e}"


@mcp.tool()
async def mouse_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    button: str = "left",
    duration: float = 0.5,
) -> str:
    """Drag from one position to another.

    Args:
        start_x, start_y: Starting coordinates.
        end_x, end_y: Ending coordinates.
        button: Mouse button to hold during drag.
        duration: Time in seconds for the drag motion.
    """
    try:
        return drag(start_x, start_y, end_x, end_y, button, duration)
    except Exception as e:
        return f"ERROR: Drag failed - {e}"


@mcp.tool()
async def mouse_scroll(
    x: int,
    y: int,
    clicks: int,
    horizontal: bool = False,
) -> str:
    """Scroll at a position.

    Args:
        x, y: Position to scroll at.
        clicks: Scroll amount. Positive = up, negative = down.
        horizontal: If True, scroll horizontally instead.
    """
    try:
        return scroll(x, y, clicks, horizontal)
    except Exception as e:
        return f"ERROR: Scroll failed - {e}"


# ── Keyboard Tools ────────────────────────────────────────────────────


@mcp.tool()
async def keyboard_type(text: str) -> str:
    """Type text at the current cursor position.

    Handles both ASCII and Unicode text. Unicode is typed via clipboard paste.

    Args:
        text: The text to type.
    """
    try:
        return type_text(text)
    except Exception as e:
        return f"ERROR: Typing failed - {e}"


@mcp.tool()
async def keyboard_hotkey(keys: list[str]) -> str:
    """Press a keyboard shortcut or key combination.

    Args:
        keys: List of keys to press together.
            Examples: ["ctrl", "c"], ["alt", "tab"], ["win"],
            ["ctrl", "shift", "esc"], ["enter"], ["tab"].
    """
    try:
        return hotkey(keys)
    except Exception as e:
        return f"ERROR: Hotkey failed - {e}"


# ── Convenience Tools ─────────────────────────────────────────────────


@mcp.tool()
async def open_application(
    name: str,
    method: str = "search",
) -> str:
    """Open an application by name.

    For Electron apps (Discord, VS Code, Slack), use method="path" to enable
    CDP-based element detection via --remote-debugging-port.

    Args:
        name: Application name (e.g. "Chrome", "Discord", "Notepad").
        method: How to open it:
            - "search" (default): Start menu search. Most reliable.
            - "run": Win+R dialog. Good for system tools.
            - "path": Direct launch. Required for Electron CDP support.
    """
    try:
        return open_app(name, method)
    except Exception as e:
        return f"ERROR: Failed to open '{name}' - {e}"


@mcp.tool()
async def click_element(
    window_title: str,
    element_name: str,
    element_type: str | None = None,
) -> str:
    """Find a UI element by name and click its center. No coordinate guessing.

    Uses CDP (Electron apps) or UIA (native apps) to find the element's
    exact bounding box, then clicks the center.

    Args:
        window_title: Window to search in (title or substring).
        element_name: Text/name of the element to click.
        element_type: Optional type filter (e.g. "Button", "ListItem").
    """
    try:
        return await element_detection.click_element(
            window_title=window_title,
            element_name=element_name,
            element_type=element_type,
        )
    except Exception as e:
        return f"ERROR: click_element failed - {e}"


@mcp.tool()
async def wait(seconds: float) -> str:
    """Wait for a specified duration. Useful for loading screens and animations.

    Args:
        seconds: How long to wait (max 30 seconds).
    """
    seconds = min(seconds, 30.0)
    time.sleep(seconds)
    return f"Waited {seconds} seconds."


@mcp.tool()
async def list_open_windows() -> str:
    """List all visible windows with titles, process names, and positions.

    Use this to understand what's currently open on the desktop.
    """
    try:
        wins = list_windows()
        if not wins:
            return "No visible windows found."

        # Format for readability, exclude hwnd
        formatted = []
        for w in wins:
            formatted.append({
                "title": w["title"],
                "process": w["process"],
                "position": f"({w['left']}, {w['top']})",
                "size": f"{w['width']}x{w['height']}",
            })
        return json.dumps(formatted, indent=2)
    except Exception as e:
        return f"ERROR: {e}"


def main():
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
