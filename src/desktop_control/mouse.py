"""Mouse control via pyautogui."""

import pyautogui

pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True


def click(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
    hold_keys: list[str] | None = None,
) -> str:
    """Click at the given coordinates.

    Args:
        x, y: Screen coordinates.
        button: "left", "right", or "middle".
        clicks: Number of clicks (2 for double-click).
        hold_keys: Modifier keys to hold during click (e.g. ["ctrl"]).
    """
    if hold_keys:
        for key in hold_keys:
            pyautogui.keyDown(key)

    pyautogui.click(x, y, clicks=clicks, button=button)

    if hold_keys:
        for key in reversed(hold_keys):
            pyautogui.keyUp(key)

    return f"Clicked {button} at ({x}, {y}), clicks={clicks}"


def drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    button: str = "left",
    duration: float = 0.5,
) -> str:
    """Drag from (start_x, start_y) to (end_x, end_y)."""
    pyautogui.moveTo(start_x, start_y)
    pyautogui.drag(
        end_x - start_x,
        end_y - start_y,
        duration=duration,
        button=button,
    )
    return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"


def scroll(
    x: int,
    y: int,
    clicks: int,
    horizontal: bool = False,
) -> str:
    """Scroll at position. Positive clicks = up, negative = down."""
    pyautogui.moveTo(x, y)
    if horizontal:
        pyautogui.hscroll(clicks)
    else:
        pyautogui.scroll(clicks)
    direction = "horizontally" if horizontal else "vertically"
    return f"Scrolled {direction} by {clicks} at ({x}, {y})"


def move(x: int, y: int, duration: float = 0.3) -> str:
    """Move mouse to position."""
    pyautogui.moveTo(x, y, duration=duration)
    return f"Moved mouse to ({x}, {y})"
