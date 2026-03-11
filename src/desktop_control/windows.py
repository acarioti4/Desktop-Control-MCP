"""Windows-specific helpers: app launching, window listing, Electron app registry."""

import ctypes
import ctypes.wintypes
import subprocess
import time

import pyautogui

# Known Electron apps with their exe names and debug ports
ELECTRON_APPS = {
    "discord": {"exe": "Discord.exe", "debug_port": 9223},
    "vscode": {"exe": "Code.exe", "debug_port": 9224},
    "visual studio code": {"exe": "Code.exe", "debug_port": 9224},
    "slack": {"exe": "slack.exe", "debug_port": 9225},
    "teams": {"exe": "ms-teams.exe", "debug_port": 9226},
    "obsidian": {"exe": "Obsidian.exe", "debug_port": 9227},
    "notion": {"exe": "Notion.exe", "debug_port": 9228},
    "spotify": {"exe": "Spotify.exe", "debug_port": 9229},
    "figma": {"exe": "Figma.exe", "debug_port": 9230},
}

# Mapping of friendly names to run commands for Win+R
RUN_COMMANDS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "snipping tool": "snippingtool.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
}


def is_electron_app(name: str) -> dict | None:
    """Check if an app name corresponds to a known Electron app.

    Returns the app info dict or None.
    """
    return ELECTRON_APPS.get(name.lower())


def open_app(name: str, method: str = "search") -> str:
    """Open an application.

    Args:
        name: Application name (e.g. "Chrome", "Discord", "Notepad").
        method: "search" (Start menu), "run" (Win+R), or "path" (direct path).

    Returns:
        Status message.
    """
    name_lower = name.lower()
    electron_info = is_electron_app(name_lower)

    if method == "search":
        return _open_via_search(name, electron_info)
    elif method == "run":
        return _open_via_run(name, name_lower)
    elif method == "path":
        return _open_via_path(name, electron_info)
    else:
        return f"ERROR: Unknown method '{method}'. Use 'search', 'run', or 'path'."


def _open_via_search(name: str, electron_info: dict | None) -> str:
    """Open app via Start menu search (most reliable method)."""
    pyautogui.press("win")
    time.sleep(0.5)
    pyautogui.typewrite(name, interval=0.05)
    time.sleep(1.0)
    pyautogui.press("enter")
    time.sleep(2.0)

    msg = f"Opened '{name}' via Start menu search."
    if electron_info:
        msg += (
            f" Note: {name} is an Electron app. For element detection, "
            f"it may need to be restarted with --remote-debugging-port={electron_info['debug_port']}. "
            f"Use open_application with method='path' to launch with CDP support."
        )
    return msg


def _open_via_run(name: str, name_lower: str) -> str:
    """Open app via Win+R run dialog."""
    cmd = RUN_COMMANDS.get(name_lower, name)
    pyautogui.hotkey("win", "r")
    time.sleep(0.5)
    pyautogui.typewrite(cmd, interval=0.03)
    pyautogui.press("enter")
    time.sleep(2.0)
    return f"Opened '{name}' via Win+R ({cmd})."


def _open_via_path(name: str, electron_info: dict | None) -> str:
    """Open app with full path support and Electron debug port."""
    if electron_info:
        return _launch_electron_with_cdp(name, electron_info)

    name_lower = name.lower()
    cmd = RUN_COMMANDS.get(name_lower, name)
    try:
        subprocess.Popen(cmd, shell=True)
        time.sleep(2.0)
        return f"Opened '{name}' via direct path ({cmd})."
    except Exception as e:
        return f"ERROR: Failed to open '{name}' - {e}"


def _launch_electron_with_cdp(name: str, info: dict) -> str:
    """Launch an Electron app with --remote-debugging-port enabled."""
    exe = info["exe"]
    port = info["debug_port"]

    # Try to find the exe path using 'where' command
    try:
        result = subprocess.run(
            ["where", exe],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            exe_path = result.stdout.strip().split("\n")[0]
        else:
            # Fall back to common install locations
            exe_path = _find_electron_exe(exe)
    except Exception:
        exe_path = _find_electron_exe(exe)

    if not exe_path:
        # Fallback: use Start menu search
        return _open_via_search(name, info)

    try:
        subprocess.Popen([exe_path, f"--remote-debugging-port={port}"])
        time.sleep(3.0)
        return (
            f"Opened '{name}' with CDP debug port {port}. "
            f"Element detection via CDP is now available."
        )
    except Exception as e:
        return f"ERROR: Failed to launch {name} with CDP - {e}. Falling back to search."


def _find_electron_exe(exe_name: str) -> str | None:
    """Search common install locations for an Electron app executable."""
    import os

    search_dirs = [
        os.path.expandvars(r"%LOCALAPPDATA%"),
        os.path.expandvars(r"%APPDATA%"),
        os.path.expandvars(r"%PROGRAMFILES%"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%"),
    ]

    for base_dir in search_dirs:
        for root, dirs, files in os.walk(base_dir):
            if exe_name in files:
                return os.path.join(root, exe_name)
            # Don't recurse too deep
            depth = root.replace(base_dir, "").count(os.sep)
            if depth >= 4:
                dirs.clear()

    return None


def list_windows() -> list[dict]:
    """List all visible windows with their titles and positions."""
    windows = []

    EnumWindows = ctypes.windll.user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    GetWindowText = ctypes.windll.user32.GetWindowTextW
    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
    IsWindowVisible = ctypes.windll.user32.IsWindowVisible
    GetWindowRect = ctypes.windll.user32.GetWindowRect

    def enum_callback(hwnd, _):
        if not IsWindowVisible(hwnd):
            return True

        length = GetWindowTextLength(hwnd)
        if length == 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buf, length + 1)
        title = buf.value

        if not title or title == "Program Manager":
            return True

        rect = ctypes.wintypes.RECT()
        GetWindowRect(hwnd, ctypes.byref(rect))

        # Get process name
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = _get_process_name(pid.value)

        windows.append({
            "title": title,
            "process": process_name,
            "hwnd": hwnd,
            "left": rect.left,
            "top": rect.top,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top,
        })
        return True

    EnumWindows(EnumWindowsProc(enum_callback), 0)
    return windows


def _get_process_name(pid: int) -> str:
    """Get process name from PID."""
    try:
        import ctypes
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010

        h_process = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid
        )
        if h_process:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.wintypes.DWORD(260)
            ctypes.windll.kernel32.QueryFullProcessImageNameW(
                h_process, 0, buf, ctypes.byref(size)
            )
            ctypes.windll.kernel32.CloseHandle(h_process)
            if buf.value:
                import os
                return os.path.basename(buf.value)
    except Exception:
        pass
    return "unknown"


def find_window_by_title(title_substring: str) -> dict | None:
    """Find the first window whose title contains the given substring."""
    for w in list_windows():
        if title_substring.lower() in w["title"].lower():
            return w
    return None
