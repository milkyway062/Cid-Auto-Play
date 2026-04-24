import logging
import time
import pygetwindow

import state
import config
import InputHandler

logger = logging.getLogger(__name__)

# Patch InputHandler.Click so all clicks go through a shared lock.
_original_click  = InputHandler.Click
_original_rclick = InputHandler.RightClick

def _locked_click(x, y, delay):
    with state._click_lock:
        _original_click(x, y, delay)

def _locked_rclick(x, y, delay):
    with state._click_lock:
        _original_rclick(x, y, delay)

InputHandler.Click       = _locked_click
InputHandler.RightClick  = _locked_rclick


def _sleep(seconds: float, step: float = 0.05) -> bool:
    """Sleep for 'seconds', checking SHUTDOWN every step. Returns True if completed."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if state.SHUTDOWN:
            return False
        time.sleep(min(step, max(0.0, deadline - time.time())))
    return True


def _key_hold(key: str, seconds: float) -> bool:
    """Hold a key for 'seconds'. Returns True if completed, False on SHUTDOWN."""
    InputHandler.KeyDown(config.KEYMAP[key])
    ok = _sleep(seconds)
    InputHandler.KeyUp(config.KEYMAP[key])
    return ok


def press(key: str) -> None:
    """Tap a key (down + 20 ms + up)."""
    try:
        InputHandler.KeyDown(config.KEYMAP[key])
        time.sleep(0.02)
        InputHandler.KeyUp(config.KEYMAP[key])
    except Exception:
        logger.exception("press(%s) failed", key)


def _update_positions():
    """Called after rejoin to refresh any position globals. No-op in this project."""
    pass


def _update_restart_coords():
    """Recalculate restart button coords from current state.dx/dy."""
    dx, dy = state.dx, state.dy
    state.RESTART_SETTINGS_BTN   = ( 26 + dx, 610 + dy)
    state.RESTART_MATCH_BTN      = (704 + dx, 292 + dy)
    state.RESTART_YES_BTN        = (351 + dx, 367 + dy)
    state.RESTART_SETTINGS_CLOSE = (758 + dx, 151 + dy)


def align_roblox(padding: int = 10) -> bool:
    """Resize Roblox to 816×638 and move it to the top-left with 'padding' px margins.
    Updates state.dx/dy. Returns True on success."""
    import pygetwindow
    for w in pygetwindow.getAllWindows():
        if w.title == "Roblox":
            try:
                w.restore()
                time.sleep(0.1)
                w.resizeTo(816, 638)
                time.sleep(0.1)
                w.moveTo(padding, padding)
                time.sleep(0.1)
                w.activate()
                state.rb_window = w
                state.dx = w.left
                state.dy = w.top
                _update_restart_coords()
                logger.info("Roblox aligned to (%d, %d) at 816×638", state.dx, state.dy)
                return True
            except Exception:
                logger.exception("align_roblox failed")
                return False
    logger.warning("align_roblox: Roblox window not found")
    return False


def extract_ps_link_code(value: str) -> str:
    """Return the bare link code from a full Roblox private-server URL or a raw code."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(value)
    qs = parse_qs(parsed.query)
    if "privateServerLinkCode" in qs:
        return qs["privateServerLinkCode"][0]
    return value


def initialize() -> bool:
    """Find the Roblox window, update coordinates. Returns True on success."""
    state.rb_window = None
    for w in pygetwindow.getAllWindows():
        if w.title == "Roblox":
            state.rb_window = w
            break
    if not state.rb_window:
        logger.error("Roblox window not found.")
        return False
    state.dx, state.dy = state.rb_window.left, state.rb_window.top
    _update_positions()
    _update_restart_coords()
    state._hotkey_registered = True
    state._initialized       = True
    logger.info("Initialized: Roblox window at (%d, %d)", state.dx, state.dy)
    return True
