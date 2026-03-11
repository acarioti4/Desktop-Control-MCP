"""Unified element detection facade.

Auto-selects CDP (for Electron apps) or UIA (for native apps) based on
the target application. Both backends return the same normalized format.
"""

from desktop_control import cdp, ui_automation, windows


async def get_elements(
    window_title: str,
    element_type: str | None = None,
    name_filter: str | None = None,
    max_depth: int = 8,
) -> list[dict]:
    """Get UI elements from any app, auto-selecting the best detection method.

    For Electron apps: uses CDP (Chrome DevTools Protocol) for full DOM access.
    For native apps: uses Windows UI Automation for accessibility tree access.

    Args:
        window_title: Window title (or substring) to find.
        element_type: Filter by type (e.g. "Button", "button", "ListItem").
        name_filter: Filter by name substring.
        max_depth: Max tree depth for UIA traversal.

    Returns:
        List of element dicts: {name, type, x, y, width, height, source}.
    """
    # Find the window to get process info
    window_info = windows.find_window_by_title(window_title)
    if not window_info:
        return [{"error": f"No window found matching '{window_title}'", "source": "none"}]

    process_name = window_info.get("process", "").lower()

    # Check if this is a known Electron app
    electron_info = _match_electron_app(process_name, window_title)

    if electron_info:
        # Try CDP first
        port = electron_info["debug_port"]
        if await cdp.is_cdp_available(port):
            elements = await cdp.get_elements(
                port=port,
                window_x=window_info.get("left", 0),
                window_y=window_info.get("top", 0),
                element_type=element_type,
                name_filter=name_filter,
            )
            if elements and not any("error" in e for e in elements):
                return elements

        # CDP not available — fall through to UIA with a note
        uia_elements = ui_automation.get_elements(
            window_title=window_title,
            element_type=element_type,
            name_filter=name_filter,
            max_depth=max_depth,
        )
        uia_elements.insert(0, {
            "warning": (
                f"{window_title} appears to be an Electron app but CDP is not available. "
                f"Restart it with open_application('{window_title}', method='path') "
                f"to enable precise element detection. Falling back to UIA (limited accuracy)."
            ),
            "source": "system",
        })
        return uia_elements

    # Native app — use UIA
    return ui_automation.get_elements(
        window_title=window_title,
        element_type=element_type,
        name_filter=name_filter,
        max_depth=max_depth,
    )


async def click_element(
    window_title: str,
    element_name: str,
    element_type: str | None = None,
) -> str:
    """Find an element by name and click its center.

    Args:
        window_title: Window title to search in.
        element_name: Element name/text to find.
        element_type: Optional type filter.

    Returns:
        Status message.
    """
    elements = await get_elements(
        window_title=window_title,
        name_filter=element_name,
        element_type=element_type,
    )

    # Filter out system messages
    candidates = [e for e in elements if "error" not in e and "warning" not in e]

    if not candidates:
        return (
            f"ERROR: No element matching '{element_name}' found in '{window_title}'. "
            f"Try using screenshot to visually locate the element."
        )

    # Find the best match (prefer exact match, then shortest name containing the filter)
    best = None
    for el in candidates:
        name = el.get("name", "")
        if name.lower() == element_name.lower():
            best = el
            break
        if best is None or len(name) < len(best.get("name", "")):
            best = el

    if not best:
        return f"ERROR: Could not determine best match for '{element_name}'."

    # Click the center of the element
    center_x = best["x"] + best["width"] // 2
    center_y = best["y"] + best["height"] // 2

    from desktop_control.mouse import click
    click(center_x, center_y)

    return (
        f"Clicked '{best['name']}' ({best['type']}) at center ({center_x}, {center_y}). "
        f"Element bounds: ({best['x']}, {best['y']}, {best['width']}x{best['height']}). "
        f"Source: {best['source']}."
    )


def _match_electron_app(process_name: str, window_title: str) -> dict | None:
    """Check if a process or window title matches a known Electron app."""
    # Check by process name
    for app_name, info in windows.ELECTRON_APPS.items():
        if info["exe"].lower() == process_name:
            return info

    # Check by window title
    return windows.is_electron_app(window_title)
