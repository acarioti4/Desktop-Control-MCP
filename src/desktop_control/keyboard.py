"""Keyboard control via pyautogui with Unicode clipboard fallback."""

import pyautogui

pyautogui.PAUSE = 0.1


def type_text(text: str) -> str:
    """Type text. Uses clipboard paste for Unicode characters.

    ASCII text is typed directly via pyautogui.typewrite.
    Non-ASCII text is copied to clipboard and pasted via Ctrl+V.
    """
    if all(ord(c) < 128 for c in text):
        pyautogui.typewrite(text, interval=0.02)
    else:
        _clipboard_paste(text)
    return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


def hotkey(keys: list[str]) -> str:
    """Press a key combination (e.g. ["ctrl", "c"], ["alt", "tab"], ["win"])."""
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)
    return f"Pressed: {' + '.join(keys)}"


def press_key(key: str, presses: int = 1, interval: float = 0.1) -> str:
    """Press a single key one or more times."""
    pyautogui.press(key, presses=presses, interval=interval)
    return f"Pressed {key} x{presses}"


def _clipboard_paste(text: str) -> None:
    """Copy text to clipboard via ctypes and paste with Ctrl+V."""
    import ctypes

    CF_UNICODETEXT = 13
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    user32.OpenClipboard(0)
    user32.EmptyClipboard()

    encoded = text.encode("utf-16-le") + b"\x00\x00"
    h_mem = kernel32.GlobalAlloc(0x0042, len(encoded))  # GMEM_MOVEABLE | GMEM_ZEROINIT
    ptr = kernel32.GlobalLock(h_mem)
    ctypes.memmove(ptr, encoded, len(encoded))
    kernel32.GlobalUnlock(h_mem)
    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
    user32.CloseClipboard()

    pyautogui.hotkey("ctrl", "v")
