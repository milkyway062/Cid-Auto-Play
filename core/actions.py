import time
import logging
import ctypes
import pyautogui

import state
import config
import helpers
import detections
import InputHandler

logger = logging.getLogger(__name__)

# TODO: fill in the x/y offset from the Roblox window top-left
# to the center of the auto play button.
AUTO_PLAY_CLICK_X = 0
AUTO_PLAY_CLICK_Y = 0


def restart_match_ingame():
    """Open settings → Restart Match → Yes → click cancelbutton →
    wait for alert_restart to disappear → close settings."""
    state._restarting.set()
    try:
        logger.info("Restarting match via settings menu")

        InputHandler.Click(*state.RESTART_SETTINGS_BTN, delay=0.1)
        time.sleep(1.0)

        InputHandler.Click(*state.RESTART_MATCH_BTN, delay=0.1)
        InputHandler.Click(*state.RESTART_YES_BTN, delay=0.2)

        cancel_loc = detections._wait_for_image("cancelbutton.png", timeout=10.0)
        if cancel_loc:
            cx, cy = pyautogui.center(cancel_loc)
            InputHandler.Click(cx, cy, delay=0.1)
            logger.info("cancelbutton clicked at (%d, %d)", cx, cy)
        else:
            logger.warning("cancelbutton not detected within 10s — restart may have failed")

        alert_timeout = time.time() + 15.0
        while time.time() < alert_timeout:
            try:
                found = pyautogui.locateOnScreen(
                    detections._img("alert_restart.png"), grayscale=True, confidence=0.7
                )
                if not found:
                    logger.info("alert_restart gone — restart fully processed")
                    break
            except pyautogui.ImageNotFoundException:
                logger.info("alert_restart gone — restart fully processed")
                break
            except Exception:
                logger.exception("restart_match_ingame: error checking alert_restart")
                break
            time.sleep(0.1)
        else:
            logger.warning("alert_restart still visible after 15s — proceeding anyway")

        time.sleep(0.2)
        InputHandler.Click(*state.RESTART_SETTINGS_CLOSE, delay=0.1)
        logger.info("Settings panel closed after restart")

    except Exception:
        logger.exception("restart_match_ingame failed")
    finally:
        state._restarting.clear()
        logger.info("restart_match_ingame: _restarting cleared")


def return_to_spawn():
    """Click through the return-to-spawn sequence."""
    logger.info("Returning to spawn")
    for pos in config.RETURN_TO_SPAWN_CLICKS:
        if state.SHUTDOWN:
            return
        InputHandler.Click(pos[0] + state.dx, pos[1] + state.dy, delay=0.2)
        helpers._sleep(0.8)
    logger.info("Return to spawn complete")


def do_positioning() -> bool:
    """Camera reset + walk to spawn + set rally point (ported from Cid-Macro-But-Better).
    Returns True if completed, False if interrupted."""
    logger.info("Starting positioning")
    if not helpers._sleep(1):
        return False

    # Open unit panel so camera keys register
    InputHandler.Click(
        config.UNIT_PANEL_POS[0] + state.dx,
        config.UNIT_PANEL_POS[1] + state.dy,
        delay=0.1,
    )

    # Camera up
    if not helpers._key_hold("i", 2):
        return False

    # Camera tilt
    ctypes.windll.user32.mouse_event(0x0001, 0, config.CAMERA_MOVE_OFFSET[1], 0, 0)
    if not helpers._sleep(1):
        return False

    # Camera reset
    if not helpers._key_hold("o", 2):
        return False

    logger.info("Camera reset complete")

    return_to_spawn()
    if not helpers._sleep(1):
        return False

    # Set rally point
    InputHandler.RightClick(282 + state.dx, 345 + state.dy, delay=0.5)
    logger.info("Positioning done")
    return True


def setup_auto_play() -> bool:
    """Configure auto play settings. Runs once per rejoin, right after positioning."""
    logger.info("Configuring auto play settings")

    def c(x, y, delay):
        if state.SHUTDOWN:
            return False
        InputHandler.Click(x + state.dx, y + state.dy, delay=delay)
        return True

    steps = [
        (672, 433, 0.4),  # open auto play settings
        (358, 296, 0.4),  # position
        (198, 336, 0.3),  # track
        (672, 432, 0.4),  # auto play settings again
        (323, 386, 0.4),  # slot 1 auto off
        (553, 417, 0.4),  # slot 2 auto upgrade off
        (364, 415, 0.5),  # slot 1 prio
        (333, 359, 0.3),  # min
        (352, 398, 0.3),  # apply
        (612, 413, 0.5),  # slot 2 prio
        (333, 359, 0.3),  # min
        (352, 398, 0.3),  # apply
        (404, 410, 0.3),  # hover mid for scroll
    ]
    for x, y, d in steps:
        if not c(x, y, d):
            return False

    InputHandler.Scroll(2)
    if not helpers._sleep(0.2):
        return False

    steps2 = [
        (312, 305, 0.4),  # slot 3 auto up off
        (286, 276, 0.3),  # slot 3 place off
        (364, 305, 0.5),  # slot 3 prio
        (333, 359, 0.3),  # min
        (352, 398, 0.3),  # apply
        (532, 277, 0.3),  # slot 4 place off
        (284, 368, 0.3),  # slot 5 place off
        (313, 395, 0.4),  # slot 5 auto up off
        (365, 393, 0.5),  # slot 5 prio
        (333, 359, 0.3),  # min
        (352, 398, 0.3),  # apply
        (570, 367, 0.3),  # slot 6 auto on
        (558, 396, 0.4),  # slot 6 auto up off
        (612, 393, 0.5),  # slot 6 prio
        (333, 359, 0.3),  # min
        (352, 398, 0.3),  # apply
        (650, 186, 0.4),  # close ui
        (162, 66, 0.1),   # close chat 1
        (162, 66, 0.1),   # close chat 2
    ]
    for x, y, d in steps2:
        if not c(x, y, d):
            return False

    logger.info("Auto play setup done")
    return True
