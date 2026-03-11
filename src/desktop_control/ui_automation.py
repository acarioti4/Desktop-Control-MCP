"""Windows UI Automation (UIA) for native app element detection.

Uses comtypes to access the Windows UI Automation COM API.
Works reliably for: File Explorer, Notepad, Settings, Office apps, WPF/WinForms apps.
"""

import comtypes
import comtypes.client


# UIA ControlType IDs
CONTROL_TYPES = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50021: "ToolBar",
    50022: "ToolTip",
    50023: "Tree",
    50024: "TreeItem",
    50025: "Custom",
    50026: "Group",
    50027: "Thumb",
    50028: "DataGrid",
    50029: "DataItem",
    50030: "Document",
    50031: "SplitButton",
    50032: "Window",
    50033: "Pane",
    50034: "Header",
    50035: "HeaderItem",
    50036: "Table",
    50037: "TitleBar",
    50038: "Separator",
}


def _get_uia():
    """Initialize and return the IUIAutomation instance."""
    return comtypes.CoCreateInstance(
        comtypes.GUID("{FF48DBA4-60EF-4201-AA87-54103EEF594E}"),  # CUIAutomation
        interface=comtypes.gen.UIAutomationClient.IUIAutomation,
    )


def _init_uia_typelib():
    """Ensure the UIAutomation type library is generated."""
    try:
        comtypes.gen.UIAutomationClient  # noqa: B018
    except AttributeError:
        comtypes.client.GetModule("UIAutomationCore.dll")


def get_elements(
    window_title: str,
    element_type: str | None = None,
    name_filter: str | None = None,
    max_depth: int = 8,
) -> list[dict]:
    """Get UI elements from a native Windows app via UIA.

    Args:
        window_title: Window title (or substring) to search for.
        element_type: Filter by type (e.g. "Button", "ListItem", "Edit").
        name_filter: Filter by name substring.
        max_depth: Maximum tree depth to traverse.

    Returns:
        List of element dicts with {name, type, x, y, width, height}.
    """
    _init_uia_typelib()
    uia = _get_uia()

    # Find the target window
    root = uia.GetRootElement()
    window = _find_window(uia, root, window_title)
    if not window:
        return []

    # Walk the element tree
    elements = []
    _walk_tree(uia, window, elements, element_type, name_filter, 0, max_depth)
    return elements


def _find_window(uia, root, title_substring: str):
    """Find a window element by title substring."""
    from comtypes.gen.UIAutomationClient import (
        TreeScope_Children,
        IUIAutomationElement,
    )

    condition = uia.CreateTrueCondition()
    children = root.FindAll(TreeScope_Children, condition)

    for i in range(children.Length):
        child = children.GetElement(i)
        try:
            name = child.CurrentName
            if name and title_substring.lower() in name.lower():
                return child
        except Exception:
            continue

    return None


def _walk_tree(
    uia,
    element,
    results: list,
    type_filter: str | None,
    name_filter: str | None,
    depth: int,
    max_depth: int,
):
    """Recursively walk the UIA element tree."""
    if depth > max_depth:
        return

    try:
        name = element.CurrentName or ""
        control_type_id = element.CurrentControlType
        control_type = CONTROL_TYPES.get(control_type_id, "Unknown")

        # Get bounding rectangle
        rect = element.CurrentBoundingRectangle
        x, y, w, h = int(rect.left), int(rect.top), int(rect.right - rect.left), int(rect.bottom - rect.top)

        # Skip invisible/zero-size elements
        if w <= 0 or h <= 0:
            pass
        elif type_filter and control_type.lower() != type_filter.lower():
            pass
        elif name_filter and name_filter.lower() not in name.lower():
            pass
        elif name:  # Only include named elements
            results.append({
                "name": name,
                "type": control_type,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "source": "uia",
            })
    except Exception:
        pass

    # Recurse into children
    try:
        from comtypes.gen.UIAutomationClient import TreeScope_Children

        condition = uia.CreateTrueCondition()
        children = element.FindAll(TreeScope_Children, condition)

        for i in range(children.Length):
            child = children.GetElement(i)
            _walk_tree(uia, child, results, type_filter, name_filter, depth + 1, max_depth)
    except Exception:
        pass
