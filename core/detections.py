import logging
import time
import os
import pyautogui

import state
import InputHandler

logger = logging.getLogger(__name__)


def _img(name: str) -> str:
    """Return absolute path for an image in the Images folder."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "Images", name)


def _wait_for_image(name: str, timeout: float = 5.0, confidence: float = 0.7) -> object:
    """Poll for an image within the Roblox window; return its Box location or None on timeout."""
    deadline = time.time() + timeout
    region = (
        (state.dx, state.dy, state.rb_window.width, state.rb_window.height)
        if state.rb_window else None
    )
    while time.time() < deadline:
        if state.SHUTDOWN:
            return None
        try:
            loc = pyautogui.locateOnScreen(
                _img(name), confidence=confidence, grayscale=True, region=region
            )
            if loc:
                return loc
        except pyautogui.ImageNotFoundException:
            pass
        except Exception:
            logger.exception("_wait_for_image(%s) error", name)
        time.sleep(0.1)
    logger.debug("_wait_for_image(%s) timed out after %.1fs", name, timeout)
    return None


def is_in_lobby() -> bool:
    """Return True if AreaIcon.png is visible within the Roblox window."""
    if not state.rb_window:
        return False
    region = (state.dx, state.dy, state.rb_window.width, state.rb_window.height)
    try:
        loc = pyautogui.locateOnScreen(
            _img("AreaIcon.png"), confidence=0.7, grayscale=True, region=region
        )
        return loc is not None
    except pyautogui.ImageNotFoundException:
        return False
    except Exception:
        logger.exception("is_in_lobby error")
        return False


def _daily_rewards_visible() -> bool:
    """Return True if the daily rewards popup is present (white pixel at 654,187)."""
    if not state.rb_window:
        return False
    try:
        return pyautogui.pixelMatchesColor(654 + state.dx, 187 + state.dy,
                                           (255, 255, 255), tolerance=5)
    except Exception:
        return False


def dismiss_passive_menu() -> bool:
    """Detect passive title on screen; if found, click its center."""
    if not state.rb_window:
        return False
    region = (state.dx, state.dy, state.rb_window.width, state.rb_window.height)
    try:
        location = pyautogui.locateOnScreen(
            image=_img("passive_title.png"),
            grayscale=True,
            confidence=0.75,
            region=region,
        )
        if location:
            cx, cy = pyautogui.center(location)
            InputHandler.Click(cx, cy, delay=0.1)
            logger.info("Passive menu detected and dismissed")
            return True
    except pyautogui.ImageNotFoundException:
        pass
    except Exception:
        logger.exception("dismiss_passive_menu failed")
    return False


def _get_pixel(x: int, y: int) -> tuple:
    try:
        return pyautogui.pixel(x, y)
    except Exception:
        return (0, 0, 0)


# ── Wave detection (OCR) ─────────────────────────────────────────────────────

_TESSERACT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tesseract", "tesseract.exe",
)

try:
    import pytesseract as _pyt
    import numpy as _np
    from PIL import Image as _Image
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

def _read_wave_number():
    if not state.rb_window:
        return None
    if not _OCR_AVAILABLE:
        logger.warning("OCR unavailable — pytesseract/numpy/PIL not installed")
        return None
    try:
        from PIL import ImageGrab

        _pyt.pytesseract.tesseract_cmd = _TESSERACT_PATH

        left   = state.dx + 195
        top    = state.dy + 52
        right  = left + 75
        bottom = top  + 22

        img = ImageGrab.grab(bbox=(left, top, right, bottom))
        w, h = img.size
        img = img.resize((w * 4, h * 4))

        arr = _np.array(img)
        mask = (arr[:, :, 0] > 200) & (arr[:, :, 1] > 200) & (arr[:, :, 2] > 200)
        out = _np.zeros_like(arr)
        out[mask]  = [0,   0,   0  ]
        out[~mask] = [255, 255, 255]

        text = _pyt.image_to_string(
            _Image.fromarray(out.astype(_np.uint8)),
            config="--psm 7 -c tessedit_char_whitelist=0123456789",
        ).strip()
        return text if text else None
    except Exception:
        logger.warning("_read_wave_number failed", exc_info=True)
        return None


_last_wave = None


def _read_wave_logged() -> str | None:
    global _last_wave
    text = _read_wave_number()
    if text != _last_wave:
        logger.info("wave %s", text)
        _last_wave = text
    return text


def is_wave0_visible() -> bool:
    return _read_wave_logged() == "0"


def wait_for_ingame(timeout: float = 300.0) -> bool:
    """Block until wave 1 or 2 is visible (confirms we're inside a match)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if state.SHUTDOWN or state._restart_run.is_set():
            return False
        if _read_wave_logged() in ("1", "2"):
            logger.info("In-game confirmed")
            return True
        time.sleep(0.25)
    logger.warning("wait_for_ingame timed out after %.1fs", timeout)
    return False


def wait_for_wave0(timeout: float = 300.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if state.SHUTDOWN or state._restart_run.is_set():
            return False
        if is_wave0_visible():
            return True
        time.sleep(0.25)
    logger.warning("wait_for_wave0 timed out after %.1fs", timeout)
    return False


def wait_for_wave0_gone(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if state.SHUTDOWN or state._restart_run.is_set():
            return False
        if not is_wave0_visible():
            return True
        time.sleep(0.25)
    return False


# ── Positioning done detection ────────────────────────────────────────────────

def wait_for_positioning_done(timeout: float = 60.0) -> bool:
    """Block until Activate.png appears (auto play finished positioning units)."""
    return _wait_for_image("Activate.png", timeout=timeout, confidence=0.8) is not None


# ── Auto play detection ───────────────────────────────────────────────────────
# TODO: set AUTO_PLAY_X, AUTO_PLAY_Y to the pixel that changes color when
#       auto play is toggled ON, and set AUTO_PLAY_COLOR to that active-state color.
AUTO_PLAY_X     = 0
AUTO_PLAY_Y     = 0
AUTO_PLAY_COLOR = (0, 0, 0)
AUTO_PLAY_TOL   = 30


def is_auto_play_active() -> bool:
    """Return True if the auto play pixel matches the active-state color."""
    r, g, b = _get_pixel(state.dx + AUTO_PLAY_X, state.dy + AUTO_PLAY_Y)
    er, eg, eb = AUTO_PLAY_COLOR
    return abs(r - er) < AUTO_PLAY_TOL and abs(g - eg) < AUTO_PLAY_TOL and abs(b - eb) < AUTO_PLAY_TOL
