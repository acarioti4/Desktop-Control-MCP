# Desktop Control MCP

An MCP server that gives LLMs the ability to see and control a Windows desktop via screenshots, mouse, keyboard, and UI element detection.

## How It Works

The server provides tools — the LLM client (Claude) does all the reasoning:

1. **Screenshot** the desktop to see what's on screen
2. **Identify** UI elements via vision or Windows UI Automation
3. **Act** using mouse clicks, keyboard input, or hotkeys
4. **Verify** by taking another screenshot after each action

### Three-Layer Element Detection

| Layer | Method | Best For |
|-------|--------|----------|
| **CDP** | Chrome DevTools Protocol via WebSocket | Electron apps (Discord, VS Code, Slack) — requires `method="path"` launch |
| **UIA** | Windows UI Automation COM API | Native apps (Notepad, Explorer, Settings, Office) |
| **Vision** | Screenshot + LLM vision | Everything else — LLM estimates coordinates from the image |

## Installation

```bash
cd Desktop-Control-MCP
pip install -e .
```

### Register with Claude Desktop

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "desktop-control": {
      "command": "python",
      "args": ["-m", "desktop_control.server"],
      "cwd": "C:\\path\\to\\Desktop-Control-MCP"
    }
  }
}
```

Then restart Claude Desktop.

## Tools (12)

### Vision & Awareness

| Tool | Description |
|------|-------------|
| `screenshot` | Capture desktop as JPEG. Returns image + screen dimensions. Coordinates map 1:1 to mouse coordinates. |
| `get_elements` | Get interactive UI elements with exact bounding boxes. Auto-selects CDP or UIA based on the app. |
| `get_screen_info` | Monitor geometries, cursor position, DPI scale. |
| `list_open_windows` | All visible windows with titles, process names, and positions. |

### Mouse

| Tool | Description |
|------|-------------|
| `mouse_click` | Click at (x, y). Supports left/right/middle, double-click, modifier keys. |
| `mouse_drag` | Drag from one point to another. |
| `mouse_scroll` | Scroll vertically or horizontally at a position. |

### Keyboard

| Tool | Description |
|------|-------------|
| `keyboard_type` | Type text. Handles Unicode via clipboard paste. |
| `keyboard_hotkey` | Press key combos like `["ctrl", "c"]`, `["alt", "tab"]`, `["win"]`. |

### Convenience

| Tool | Description |
|------|-------------|
| `open_application` | Open an app by name via Start menu search, Win+R, or direct path. |
| `click_element` | Find a UI element by name and click its center — no coordinate guessing. |
| `wait` | Pause for loading screens (max 30s). |

## Project Structure

```
src/desktop_control/
  server.py           # FastMCP server, all tool definitions, entry point
  screen.py           # DPI awareness init, screenshot capture via mss
  mouse.py            # Click, drag, scroll via pyautogui
  keyboard.py         # Text typing with Unicode clipboard fallback, hotkeys
  ui_automation.py    # Windows UI Automation (native app element detection)
  cdp.py              # Chrome DevTools Protocol (Electron app element detection)
  element_detection.py # Unified facade — auto-selects CDP or UIA
  windows.py          # App launching, window enumeration, Electron app registry
```

## Dependencies

- `mcp` — MCP Python SDK (FastMCP)
- `pyautogui` — Mouse/keyboard control
- `Pillow` — Image processing
- `mss` — Fast multi-monitor screenshots
- `comtypes` — Windows UI Automation COM access
- `websockets` + `aiohttp` — CDP communication for Electron apps

## Key Technical Details

### DPI Awareness

`screen.py` calls `SetProcessDpiAwareness(2)` at module level **before** any GUI library imports. This ensures `mss` captures at physical pixel resolution and `pyautogui` coordinates match screen pixels. The server import order in `server.py` enforces this.

### Screenshot Coordinates

Screenshots default to `monitor_index=1` (primary monitor). Using `monitor_index=0` captures the virtual combined monitor which has different dimensions — this caused a ~40% coordinate mismatch on systems where the virtual and primary monitor sizes differ.

Region screenshots include offset instructions so the LLM can map pixel positions back to screen coordinates.

### Electron App Support

Electron apps (Discord, VS Code, Slack, etc.) expose limited UIA elements. For full DOM access, launch them with `open_application(name, method="path")` which adds `--remote-debugging-port`. Known apps and their debug ports are registered in `windows.py:ELECTRON_APPS`.

### Safety

- `pyautogui.FAILSAFE = True` — move mouse to top-left corner (0,0) to abort
- `wait` capped at 30 seconds to prevent hangs
- Cannot interact with UAC prompts (secure desktop)

## Example Usage

From Claude Desktop (after registering the MCP server):

> "Open Discord and join the General voice channel on the rick_ server"

The LLM will:
1. `open_application("Discord")` or click the taskbar icon
2. `screenshot()` to see the Discord window
3. `mouse_click()` on the correct server icon
4. `screenshot()` to verify navigation
5. `mouse_click()` on the voice channel
6. `screenshot()` to confirm joined
