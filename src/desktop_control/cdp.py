"""Chrome DevTools Protocol (CDP) for Electron app element detection.

Connects to Electron apps via --remote-debugging-port to query the DOM
and get exact element positions. No Selenium dependency — uses raw WebSocket.
"""

import asyncio
import json

import aiohttp
import websockets


async def discover_debug_url(port: int) -> str | None:
    """Discover the WebSocket debug URL for a CDP-enabled app.

    Connects to http://localhost:{port}/json to find the first page target.
    """
    url = f"http://localhost:{port}/json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status != 200:
                    return None
                targets = await resp.json()
                for target in targets:
                    if target.get("type") == "page":
                        return target.get("webSocketDebuggerUrl")
                # If no page type, return the first target
                if targets:
                    return targets[0].get("webSocketDebuggerUrl")
    except Exception:
        return None
    return None


async def is_cdp_available(port: int) -> bool:
    """Check if a CDP debug port is responding."""
    return await discover_debug_url(port) is not None


async def get_elements(
    port: int,
    window_x: int = 0,
    window_y: int = 0,
    element_type: str | None = None,
    name_filter: str | None = None,
) -> list[dict]:
    """Get interactive elements from an Electron app via CDP.

    Args:
        port: The remote debugging port.
        window_x: Window left position (to convert page coords to screen coords).
        window_y: Window top position (to convert page coords to screen coords).
        element_type: Filter by element type (e.g. "button", "link", "input").
        name_filter: Filter by text content substring.

    Returns:
        List of element dicts with {name, type, x, y, width, height, source}.
    """
    ws_url = await discover_debug_url(port)
    if not ws_url:
        return []

    # JavaScript to find all interactive elements and their bounding rects
    js_code = """
    (() => {
        const selectors = [
            'button', 'a', 'input', 'select', 'textarea',
            '[role="button"]', '[role="link"]', '[role="tab"]',
            '[role="menuitem"]', '[role="option"]', '[role="listbox"]',
            '[role="treeitem"]', '[role="checkbox"]', '[role="radio"]',
            '[role="switch"]', '[role="slider"]',
            '[tabindex]', '[onclick]', '[data-list-item-id]',
            '[class*="clickable"]', '[class*="interactive"]',
        ];
        const seen = new Set();
        const results = [];

        for (const sel of selectors) {
            try {
                for (const el of document.querySelectorAll(sel)) {
                    if (seen.has(el)) continue;
                    seen.add(el);

                    const rect = el.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) continue;

                    // Skip elements not visible in viewport
                    if (rect.bottom < 0 || rect.right < 0) continue;

                    const text = (
                        el.textContent?.trim()?.substring(0, 100) ||
                        el.getAttribute('aria-label') ||
                        el.getAttribute('title') ||
                        el.getAttribute('placeholder') ||
                        el.getAttribute('alt') ||
                        ''
                    );

                    const role = el.getAttribute('role') || el.tagName.toLowerCase();

                    results.push({
                        name: text,
                        type: role,
                        tag: el.tagName.toLowerCase(),
                        x: Math.round(rect.left),
                        y: Math.round(rect.top),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                    });
                }
            } catch(e) {}
        }

        return results;
    })()
    """

    try:
        async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
            msg = json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_code,
                    "returnByValue": True,
                },
            })
            await ws.send(msg)

            response = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(response)

            result = data.get("result", {}).get("result", {}).get("value", [])
            if not isinstance(result, list):
                return []

            # Get window chrome offset (title bar, etc.)
            # We need to account for the difference between window position
            # and the content area. Query the window's devicePixelRatio and offsets.
            offset_js = """
            (() => ({
                offsetX: window.screenX || window.screenLeft || 0,
                offsetY: window.screenY || window.screenTop || 0,
                outerWidth: window.outerWidth,
                outerHeight: window.outerHeight,
                innerWidth: window.innerWidth,
                innerHeight: window.innerHeight,
                dpr: window.devicePixelRatio || 1,
            }))()
            """
            msg2 = json.dumps({
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": offset_js,
                    "returnByValue": True,
                },
            })
            await ws.send(msg2)
            response2 = await asyncio.wait_for(ws.recv(), timeout=5)
            data2 = json.loads(response2)
            offsets = data2.get("result", {}).get("result", {}).get("value", {})

            screen_x = offsets.get("offsetX", window_x)
            screen_y = offsets.get("offsetY", window_y)
            dpr = offsets.get("dpr", 1)

            # Calculate content area offset (window chrome)
            outer_h = offsets.get("outerHeight", 0)
            inner_h = offsets.get("innerHeight", 0)
            outer_w = offsets.get("outerWidth", 0)
            inner_w = offsets.get("innerWidth", 0)
            chrome_top = outer_h - inner_h  # title bar + menu bar height
            chrome_left = (outer_w - inner_w) // 2  # window border

            elements = []
            for el in result:
                name = el.get("name", "")
                el_type = el.get("type", "")

                # Apply filters
                if element_type and el_type.lower() != element_type.lower():
                    continue
                if name_filter and name_filter.lower() not in name.lower():
                    continue

                # Convert page coordinates to screen coordinates
                abs_x = screen_x + chrome_left + int(el["x"] * dpr)
                abs_y = screen_y + chrome_top + int(el["y"] * dpr)
                abs_w = int(el["width"] * dpr)
                abs_h = int(el["height"] * dpr)

                elements.append({
                    "name": name,
                    "type": el_type,
                    "tag": el.get("tag", ""),
                    "x": abs_x,
                    "y": abs_y,
                    "width": abs_w,
                    "height": abs_h,
                    "source": "cdp",
                })

            return elements

    except Exception as e:
        return [{"error": f"CDP connection failed: {str(e)}", "source": "cdp"}]
