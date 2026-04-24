import threading

# =========================
# Roblox window state
# =========================
rb_window = None
dx = 0
dy = 0

# =========================
# Runtime-mutable settings
# =========================
PRIVATE_SERVER_CODE    = ""
AUTO_REJOIN_AFTER_RUNS = 0
WEBHOOK_URL            = ""

# =========================
# Shared state dict (read by GUI tick loop)
# =========================
state = {
    "runs":              0,
    "runs_since_rejoin": 0,
    "session_start":     0.0,
    "run_start":         0.0,
    "total_run_time":    0.0,
    "running":           False,
    "last_webhook_ok":   None,
}

# =========================
# Runtime flags
# =========================
SHUTDOWN             = False
LAST_WEBHOOK_OK      = True
LAST_WEBHOOK_ATTEMPT = 0.0

# =========================
# Thread synchronization
# =========================
_click_lock  = threading.Lock()
_restart_run = threading.Event()   # set to abort current wait (disconnect, stop)
_rejoining   = threading.Event()   # set while disconnect_checker is mid-rejoin
_restarting  = threading.Event()   # set during restart_match_ingame

# Restart button coords (set by helpers.initialize)
RESTART_SETTINGS_BTN   = (0, 0)
RESTART_MATCH_BTN      = (0, 0)
RESTART_YES_BTN        = (0, 0)
RESTART_SETTINGS_CLOSE = (0, 0)

# =========================
# Thread handles
# =========================
_initialized       = False
_hotkey_registered = False
_macro_thread      = None
