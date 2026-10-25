"""
Window capture for vision input.

Uses pygetwindow to find a window by title and Pillow to grab its region.
Falls back to full primary monitor if no window title is configured or the
window cannot be found.

Requirements: pygetwindow, Pillow (already installed)
  pip install pygetwindow
"""

import logging
from PIL import Image, ImageGrab

logger = logging.getLogger(__name__)


def list_windows() -> list[str]:
    """Return titles of all currently visible windows."""
    try:
        import pygetwindow as gw
        return [w.title for w in gw.getAllWindows() if w.title.strip()]
    except Exception as exc:
        logger.warning("[list_windows] Failed to list windows: %s", exc)
        return []


def capture_window(title: str | None) -> Image.Image | None:
    """
    Capture a specific window by title and return a PIL Image.
    If title is None or the window cannot be found, falls back to full screen.
    Resizes to a maximum of 1024px on the longest side to reduce model input cost.
    """
    bbox = None

    if title:
        try:
            import pygetwindow as gw
            matches = gw.getWindowsWithTitle(title)
            if matches:
                win = matches[0]
                bbox = (win.left, win.top, win.right, win.bottom)
            else:
                logger.warning("[capture_window] Window '%s' not found — falling back to full screen", title)
        except Exception as exc:
            logger.warning("[capture_window] pygetwindow error: %s", exc)

    try:
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
    except Exception as exc:
        logger.error("[capture_window] Screen capture failed: %s", exc)
        return None

    img = _resize(img, max_side=1024)
    return img


def _resize(img: Image.Image, max_side: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    scale = max_side / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)