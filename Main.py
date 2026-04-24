import logging
import time
import sys
import os
from threading import Thread

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

import state
import helpers
import detections
import actions
import lobby
import watchdogs
import webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main_loop():
    logger.info("Main loop started")
    auto_play_activated = False
    last_wave0_time     = 0.0

    while not state.SHUTDOWN:
        state._restart_run.clear()

        # Block while disconnect_checker is mid-rejoin
        while state._rejoining.is_set():
            if state.SHUTDOWN:
                break
            time.sleep(0.5)

        if state.SHUTDOWN:
            break

        # Navigate lobby whenever we land in it (first start, after any rejoin)
        if detections.is_in_lobby() or detections._daily_rewards_visible():
            logger.info("In lobby — preparing and navigating to Cid Raid")
            lobby.prepare_lobby()
            if state.SHUTDOWN:
                break
            lobby.lobby_path_cid_raid()
            if state.SHUTDOWN:
                break
            auto_play_activated = False
            last_wave0_time     = 0.0

        if not auto_play_activated:
            # First entry: wait for wave 1/2 to confirm we're in a match,
            # position units, set up auto play, then restart for a clean run.
            logger.info("Waiting to enter match (wave 1 or 2)...")
            if not detections.wait_for_ingame():
                if state.SHUTDOWN:
                    break
                continue
            actions.do_positioning()
            # actions.setup_auto_play()  # disabled — settings persist in-game
            auto_play_activated = True
            logger.info("Auto play set up — restarting match for clean run")
            actions.restart_match_ingame()
            helpers._sleep(2)
            actions.start_clicker()
            last_wave0_time = 0.0
            continue

        # Subsequent runs: wait for wave 0 (round start)
        logger.info("Waiting for wave 0 (round start)...")
        if not detections.wait_for_wave0():
            if state.SHUTDOWN:
                break
            continue

        now = time.time()

        # Skip count/webhook on very first wave 0 (just entered game, nothing completed yet)
        if last_wave0_time > 0:
            run_elapsed = now - last_wave0_time
            state.state["total_run_time"] += run_elapsed
            run_time_str = time.strftime("%H:%M:%S", time.gmtime(run_elapsed))
            state.state["runs"]           += 1
            state.state["runs_since_rejoin"] += 1
            run_num = state.state["runs"]
            logger.info("==== Run %d ====", run_num)
            session_elapsed = now - state.state["session_start"]
            Thread(
                target=webhook.send_webhook,
                args=(run_time_str, "", state.state["runs"],
                      state.state["runs_since_rejoin"], session_elapsed,
                      state.state["total_run_time"]),
                daemon=True,
            ).start()

        last_wave0_time          = now
        state.state["run_start"] = now

        detections.wait_for_wave0_gone()

        # Wait for wave 1 to confirm match is running, then give it 20s before checking wave 0 again
        if detections.wait_for_ingame(timeout=60):
            helpers._sleep(20)
        actions.start_clicker()

        # Auto-rejoin threshold check
        if (state.AUTO_REJOIN_AFTER_RUNS > 0
                and state.state["runs"] >= state.AUTO_REJOIN_AFTER_RUNS):
            logger.info(
                "Auto rejoin threshold %d reached — restarting Roblox",
                state.AUTO_REJOIN_AFTER_RUNS,
            )
            state.state["runs"]              = 0
            state.state["runs_since_rejoin"] = 0
            last_wave0_time                  = 0.0
            actions.stop_clicker()
            lobby.auto_rejoin()
            auto_play_activated = False

    logger.info("Main loop exiting (SHUTDOWN=%s)", state.SHUTDOWN)


def start() -> bool:
    """Start the macro in a background thread. Returns False if Roblox not found."""
    if not helpers.initialize():
        return False
    state.SHUTDOWN                    = False
    state.state["running"]            = True
    state.state["runs"]               = 0
    state.state["runs_since_rejoin"]  = 0
    state.state["session_start"]      = time.time()
    state.state["run_start"]          = 0.0
    state.state["total_run_time"]     = 0.0

    Thread(target=watchdogs.disconnect_checker, daemon=True).start()
    Thread(target=watchdogs.popup_watcher,      daemon=True).start()

    state._macro_thread = Thread(target=main_loop, daemon=True)
    state._macro_thread.start()
    return True


def stop():
    """Stop the macro cooperatively."""
    state.SHUTDOWN           = True
    state._restart_run.set()
    state.state["running"]   = False
    state.state["run_start"] = 0.0
    logger.info("Macro stop requested.")
