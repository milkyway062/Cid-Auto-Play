import logging
import time

import state
import detections
import lobby

logger = logging.getLogger(__name__)


def popup_watcher():
    """Daemon thread: continuously dismiss passive menu popups."""
    logger.info("Popup watcher started")
    while not state.SHUTDOWN:
        try:
            if detections.dismiss_passive_menu():
                time.sleep(1.5)  # cooldown — let menu fully close before rechecking
                continue
        except Exception:
            logger.exception("popup_watcher error")
        time.sleep(0.5)


def disconnect_checker():
    """Daemon thread: watches for Roblox disconnect and rejoins automatically."""
    logger.info("Disconnect checker started")
    while not state.SHUTDOWN:
        try:
            if detections._wait_for_image("Disconnected.png", timeout=2.0, confidence=0.9):
                logger.warning("Disconnect detected — rejoining")
                state._restart_run.set()
                state._rejoining.set()
                ok = lobby._do_roblox_rejoin("Disconnect")
                state._rejoining.clear()
                if ok:
                    logger.info("Rejoin successful, macro will restart run")
                else:
                    logger.error("Rejoin failed")
        except Exception:
            logger.exception("disconnect_checker error")
        time.sleep(2)
    logger.info("Disconnect checker stopped")
