import tkinter as tk
import threading
import time
import logging
import queue
import sys
import os
import json
import keyboard
import ctypes

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, "core"))
import Main
import state

_APPDATA    = os.environ.get("APPDATA", os.path.expanduser("~"))
_CONFIG_DIR = os.path.join(_APPDATA, "CidAutoPlay")
os.makedirs(_CONFIG_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(_CONFIG_DIR, "config.json")

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_config(data: dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# ── Palette (warm charcoal + amber) ───────────────────────────
BG      = "#1a1814"
SURFACE = "#211f1a"
CARD    = "#272420"
BORDER  = "#38342d"
ENTRY   = "#1e1c18"
FG      = "#e8e0d0"
FG_DIM  = "#8a7f6e"
SEL_BG  = "#38342d"
GREEN   = "#7dbb6e";  GREEN_A  = "#5d9a50"
RED     = "#cc5f5f";  RED_A    = "#a84545"
AMBER   = "#d4922a";  AMBER_A  = "#b87820"

_DOT_IDLE = "#5a5345"
_DOT_RUN  = GREEN
_DOT_STOP = "#c9a84c"
_DOT_ERR  = RED

FONT_BODY  = ("Segoe UI", 10)
FONT_LABEL = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_TITLE = ("Segoe UI Semibold", 11)
FONT_STAT  = ("Segoe UI Semibold", 20)
FONT_MONO  = ("Consolas", 9)


def _hover(widget, normal: str, active: str):
    widget.bind("<Enter>", lambda _: widget.config(bg=active))
    widget.bind("<Leave>", lambda _: widget.config(bg=normal))


class _QueueHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.log_queue = q

    def emit(self, record):
        try:
            self.log_queue.put_nowait(self.format(record))
        except queue.Full:
            pass


class MacroGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cid Auto Play")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self._log_queue: queue.Queue = queue.Queue(maxsize=500)
        self._stopping   = False
        self._cfg        = _load_config()
        self._pulse_state = False

        self._attach_log_handler()
        self._build_ui()
        self._apply_config()
        self._tick()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        keyboard.on_press_key("f1", lambda _: self.root.after(0, self._on_start))
        keyboard.on_press_key("f3", lambda _: self.root.after(0, self._on_stop))

    # ── Low-level helpers ─────────────────────────────────────

    def _card(self, parent, title=None):
        if title:
            tk.Label(
                parent, text=title.upper(), bg=BG,
                fg=FG_DIM, font=FONT_SMALL, anchor="w",
            ).pack(fill="x", padx=16, pady=(10, 2))

        outer = tk.Frame(parent, bg=BORDER)
        outer.pack(fill="x", padx=12, pady=(0, 8))

        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill="x", padx=1, pady=1)
        return outer, inner

    def _btn(self, parent, text, command, bg, active_bg,
             width=None, font=FONT_BODY, state="normal"):
        kw = dict(
            bg=bg, fg=FG, activebackground=active_bg, activeforeground=FG,
            relief="flat", bd=0, cursor="hand2",
            font=font, command=command, state=state,
            padx=14, pady=7,
        )
        if width:
            kw["width"] = width
        btn = tk.Button(parent, text=text, **kw)
        _hover(btn, bg, active_bg)
        return btn

    def _entry(self, parent, textvariable, width=None):
        kw = dict(
            textvariable=textvariable,
            bg=ENTRY, fg=FG, insertbackground=FG,
            selectbackground=SEL_BG, selectforeground=FG,
            relief="flat", bd=0, font=FONT_BODY,
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=AMBER,
        )
        if width:
            kw["width"] = width
        return tk.Entry(parent, **kw)

    def _lbl(self, parent, text="", textvariable=None, fg=FG_DIM,
             font=FONT_LABEL, anchor="w", bg=CARD, **kw):
        cfg = dict(bg=bg, fg=fg, anchor=anchor, font=font, **kw)
        if textvariable:
            cfg["textvariable"] = textvariable
        else:
            cfg["text"] = text
        return tk.Label(parent, **cfg)

    def _chk(self, parent, text, variable, command=None, bg=BG):
        return tk.Checkbutton(
            parent, text=text, variable=variable, command=command,
            bg=bg, fg=FG, selectcolor=ENTRY, font=FONT_LABEL,
            activebackground=bg, activeforeground=FG,
            bd=0, cursor="hand2",
        )

    def _sep(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=0, pady=0)

    def _attach_log_handler(self):
        h = _QueueHandler(self._log_queue)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(h)

    # ── UI construction ───────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_controls_card()
        self._build_stats_card()
        self._build_settings_card()
        self._build_footer()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(12, 4))

        tk.Label(hdr, text="◆", bg=BG, fg=AMBER,
                 font=("Segoe UI", 13)).pack(side="left")
        tk.Label(hdr, text="  Cid Auto Play", bg=BG, fg=FG,
                 font=FONT_TITLE).pack(side="left")

        pill = tk.Frame(hdr, bg=BG)
        pill.pack(side="right")

        self._status_dot = tk.Canvas(
            pill, width=8, height=8, bg=BG, highlightthickness=0,
        )
        self._status_dot.pack(side="left", padx=(0, 5), pady=2)
        self._dot_id = self._status_dot.create_oval(1, 1, 7, 7, fill=_DOT_IDLE, outline="")

        self._status_var = tk.StringVar(value="idle")
        tk.Label(pill, textvariable=self._status_var,
                 bg=BG, fg=FG_DIM, font=FONT_LABEL).pack(side="left")

    def _build_controls_card(self):
        _, inner = self._card(self.root, "controls")

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x", padx=12, pady=10)

        self._start_btn = self._btn(row, "Start  F1", self._on_start, GREEN, GREEN_A)
        self._start_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = self._btn(row, "Stop  F3", self._on_stop,
                                   RED, RED_A, state="disabled")
        self._stop_btn.pack(side="left")

        self._restart_btn = self._btn(row, "↺ Restart", self._on_restart, AMBER, AMBER_A)
        self._restart_btn.pack(side="left", padx=(8, 0))

        self._align_btn = self._btn(row, "⊡ Align", self._on_align, SURFACE, BORDER,
                                    font=FONT_LABEL)
        self._align_btn.config(highlightthickness=1, highlightbackground=BORDER,
                               highlightcolor=AMBER)
        self._align_btn.pack(side="left", padx=(8, 0))

        tk.Label(row, text="F1 / F3", bg=CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(side="right", padx=4)

    def _build_stats_card(self):
        _, inner = self._card(self.root, "stats")

        # Counters row
        counter_row = tk.Frame(inner, bg=CARD)
        counter_row.pack(fill="x", padx=12, pady=(10, 2))

        self._runs_var         = tk.StringVar(value="0")
        self._since_rejoin_var = tk.StringVar(value="0")

        for var, label in (
            (self._runs_var,         "Total Runs"),
            (self._since_rejoin_var, "Since Rejoin"),
        ):
            blk = tk.Frame(counter_row, bg=CARD)
            blk.pack(side="left", padx=(0, 24))
            tk.Label(blk, textvariable=var, bg=CARD, fg=FG,
                     font=FONT_STAT).pack(anchor="w")
            tk.Label(blk, text=label, bg=CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w")

        # Timers row
        self._sep(inner)
        timer_row = tk.Frame(inner, bg=CARD)
        timer_row.pack(fill="x", padx=12, pady=(6, 10))

        self._sess_var     = tk.StringVar(value="00:00:00")
        self._run_time_var = tk.StringVar(value="00:00:00")

        for prefix, var, store_attr in (
            ("Session", self._sess_var, None),
            ("Run",     self._run_time_var, "_run_time_lbl"),
        ):
            blk = tk.Frame(timer_row, bg=CARD)
            blk.pack(side="left", padx=(0, 24))
            tk.Label(blk, text=prefix, bg=CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left", padx=(0, 4))
            lbl = tk.Label(blk, textvariable=var, bg=CARD, fg=FG, font=FONT_LABEL)
            lbl.pack(side="left")
            if store_attr:
                setattr(self, store_attr, lbl)

    def _build_settings_card(self):
        _, inner = self._card(self.root, "settings")

        pad = {"padx": 12, "pady": 4}

        # Rejoin threshold
        row1 = tk.Frame(inner, bg=CARD)
        row1.pack(fill="x", **pad)

        self._lbl(row1, "Rejoin after", bg=CARD).pack(side="left", padx=(0, 4))
        self._rejoin_var = tk.StringVar(value=str(state.AUTO_REJOIN_AFTER_RUNS))
        self._rejoin_entry = self._entry(row1, self._rejoin_var, width=5)
        self._rejoin_entry.pack(side="left", padx=(0, 4))
        self._rejoin_entry.bind("<Return>",   self._apply_rejoin)
        self._rejoin_entry.bind("<FocusOut>", self._apply_rejoin)
        self._lbl(row1, "runs  (0 = off)", bg=CARD).pack(side="left")

        # Private server
        row2 = tk.Frame(inner, bg=CARD)
        row2.pack(fill="x", **pad)

        self._lbl(row2, "Private server", bg=CARD, width=13).pack(side="left", padx=(0, 4))
        self._ps_var = tk.StringVar(value=state.PRIVATE_SERVER_CODE)
        self._ps_entry = self._entry(row2, self._ps_var)
        self._ps_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._ps_entry.bind("<FocusOut>", self._apply_private_server)
        self._ps_entry.bind("<Return>",   self._apply_private_server)

        join_btn = self._btn(row2, "Join PS", self._on_join_ps, AMBER, AMBER_A, font=FONT_LABEL)
        join_btn.pack(side="left")

        # Webhook
        row3 = tk.Frame(inner, bg=CARD)
        row3.pack(fill="x", padx=12, pady=(4, 10))

        self._lbl(row3, "Webhook URL", bg=CARD, width=13).pack(side="left", padx=(0, 4))
        self._wh_var = tk.StringVar()
        if state.WEBHOOK_URL.startswith("https://"):
            self._wh_var.set(state.WEBHOOK_URL)
        self._wh_entry = self._entry(row3, self._wh_var)
        self._wh_entry.pack(side="left", fill="x", expand=True)
        self._wh_entry.bind("<FocusOut>", lambda _: self._save())
        self._wh_entry.bind("<Return>",   lambda _: self._save())

    def _build_footer(self):
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill="x", padx=12, pady=(0, 8))

        self._show_log = tk.BooleanVar(value=False)
        self._chk(foot, "Show log", self._show_log,
                  self._toggle_log, bg=BG).pack(side="left")

        self._update_btn = self._btn(
            foot, "Check for Updates", self._on_update,
            SURFACE, BORDER, font=FONT_LABEL,
        )
        self._update_btn.config(highlightthickness=1,
                                highlightbackground=BORDER,
                                highlightcolor=AMBER)
        self._update_btn.pack(side="right")

        # Log panel
        self._log_frame = tk.Frame(self.root, bg=SURFACE)
        self._log_frame.pack(fill="x", padx=12, pady=(0, 8))
        self._log_frame.pack_forget()

        self._log_text = tk.Text(
            self._log_frame, height=12, width=68,
            state="disabled", wrap="word",
            font=FONT_MONO,
            bg=SURFACE, fg=FG_DIM,
            insertbackground=FG,
            selectbackground=SEL_BG,
            relief="flat", bd=0,
            padx=8, pady=6,
        )
        _sb = tk.Scrollbar(
            self._log_frame, command=self._log_text.yview,
            bg=SURFACE, troughcolor=BG,
        )
        self._log_text.configure(yscrollcommand=_sb.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        _sb.pack(side="right", fill="y")

    # ── Config ────────────────────────────────────────────────

    def _apply_config(self):
        cfg = self._cfg
        if "webhook_url" in cfg:
            self._wh_var.set(cfg["webhook_url"])
            state.WEBHOOK_URL = cfg["webhook_url"]
        if "private_server" in cfg:
            self._ps_var.set(cfg["private_server"])
            state.PRIVATE_SERVER_CODE = cfg["private_server"]
        if "auto_rejoin_runs" in cfg:
            val = max(0, min(1000, int(cfg["auto_rejoin_runs"])))
            self._rejoin_var.set(str(val))
            state.AUTO_REJOIN_AFTER_RUNS = val

    def _save(self):
        _save_config({
            "webhook_url":      self._wh_var.get().strip(),
            "private_server":   self._ps_var.get().strip(),
            "auto_rejoin_runs": self._rejoin_var.get().strip(),
        })

    # ── Callbacks ─────────────────────────────────────────────

    def _on_start(self):
        state.WEBHOOK_URL         = self._wh_var.get().strip()
        state.PRIVATE_SERVER_CODE = self._ps_var.get().strip()
        self._apply_rejoin()
        self._save()
        ok = Main.start()
        if ok:
            self._start_btn.config(state="disabled")
            self._stop_btn.config(state="normal")
            self._set_status("running", _DOT_RUN)
            self._stopping = False
        else:
            self._set_status("error: Roblox not found", _DOT_ERR)

    def _on_stop(self):
        Main.stop()
        self._stop_btn.config(state="disabled")
        self._set_status("stopping…", _DOT_STOP)
        self._stopping = True

    def _on_restart(self):
        self._save()
        Main.stop()
        self._restart_btn.config(state="disabled")
        self._set_status("restarting…", _DOT_STOP)
        self.root.after(400, self._do_restart)

    def _do_restart(self):
        self.root.destroy()
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        os._exit(0)

    def _set_status(self, text: str, dot_color: str):
        self._status_var.set(text)
        self._status_dot.itemconfig(self._dot_id, fill=dot_color)

    def _apply_rejoin(self, _event=None):
        try:
            val = max(0, min(1000, int(self._rejoin_var.get())))
            state.AUTO_REJOIN_AFTER_RUNS = val
            self._rejoin_var.set(str(val))
            self._rejoin_entry.config(highlightbackground=BORDER)
            self._save()
        except ValueError:
            self._rejoin_entry.config(highlightbackground=RED)
            self.root.after(800, lambda: self._rejoin_entry.config(highlightbackground=BORDER))
            self._rejoin_var.set(str(state.AUTO_REJOIN_AFTER_RUNS))

    def _apply_private_server(self, _event=None):
        state.PRIVATE_SERVER_CODE = self._ps_var.get().strip()
        self._save()

    def _on_join_ps(self):
        import subprocess
        code = self._ps_var.get().strip()
        if not code:
            self._set_status("no private server link set", _DOT_ERR)
            return
        from helpers import extract_ps_link_code
        url = f"roblox://placeId=16146832113&linkCode={extract_ps_link_code(code)}/"
        try:
            os.startfile(url)
        except Exception:
            try:
                subprocess.Popen(["start", url], shell=True)
            except Exception:
                self._set_status("failed to open Roblox", _DOT_ERR)

    def _on_align(self):
        import helpers
        ok = helpers.align_roblox(padding=10)
        if ok:
            self._set_status("Roblox aligned", _DOT_IDLE)
            self.root.after(2000, lambda: self._set_status("idle", _DOT_IDLE))
        else:
            self._set_status("Roblox window not found", _DOT_ERR)
            self.root.after(2000, lambda: self._set_status("idle", _DOT_IDLE))

    def _on_update(self):
        self._update_btn.config(state="disabled", text="Checking...")
        self._set_status("Checking for updates...", _DOT_IDLE)
        threading.Thread(target=self._run_update, daemon=True).start()

    def _run_update(self):
        import hashlib
        import urllib.request

        REPO      = "milkyway062/Cid-Auto-Play"
        BASE_API  = f"https://api.github.com/repos/{REPO}"
        BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
        SKIP_DIRS = {"__pycache__", ".git", ".claude"}

        def git_blob_sha(path):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
            except FileNotFoundError:
                return None

        def fetch(url):
            req = urllib.request.Request(url, headers={"User-Agent": "CidAutoPlay-Updater"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read()

        def set_status(msg):
            self.root.after(0, lambda m=msg: self._set_status(m, _DOT_IDLE))

        try:
            repo_info = json.loads(fetch(BASE_API))
            branch    = repo_info.get("default_branch", "main")

            set_status("Fetching file list...")
            tree_data = json.loads(fetch(f"{BASE_API}/git/trees/{branch}?recursive=1"))

            to_update = []
            for item in tree_data.get("tree", []):
                if item["type"] != "blob":
                    continue
                path  = item["path"]
                parts = path.replace("\\", "/").split("/")
                if any(p in SKIP_DIRS for p in parts[:-1]):
                    continue
                local_path = os.path.join(BASE_DIR, *parts)
                if git_blob_sha(local_path) != item["sha"]:
                    to_update.append((path, parts))

            if not to_update:
                set_status("Already up to date!")
                self.root.after(3000, lambda: self._set_status("idle", _DOT_IDLE))
                return

            for i, (path, parts) in enumerate(to_update):
                set_status(f"Updating {parts[-1]} ({i + 1}/{len(to_update)})...")
                data       = fetch(f"https://raw.githubusercontent.com/{REPO}/{branch}/{path}")
                local_path = os.path.join(BASE_DIR, *parts)
                os.makedirs(os.path.dirname(local_path) or BASE_DIR, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(data)

            set_status(f"Updated {len(to_update)} file(s) — restart to apply.")

        except Exception as e:
            self.root.after(0, lambda: self._set_status(f"Update failed: {e}", _DOT_ERR))
        finally:
            self.root.after(0, lambda: self._update_btn.config(
                state="normal", text="Check for Updates"
            ))

    def _toggle_log(self):
        if self._show_log.get():
            self._log_frame.pack(fill="x", padx=12, pady=(0, 8))
        else:
            self._log_frame.pack_forget()
        self.root.update_idletasks()

    # ── Tick ──────────────────────────────────────────────────

    @staticmethod
    def _fmt(s: float) -> str:
        s = int(max(0, s))
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

    def _tick(self):
        st = state.state
        self._runs_var.set(str(st["runs"]))
        self._since_rejoin_var.set(str(st["runs_since_rejoin"]))

        if st["session_start"] > 0 and st["running"]:
            self._sess_var.set(self._fmt(time.time() - st["session_start"]))

        if st["running"] and st["run_start"] > 0:
            elapsed = time.time() - st["run_start"]
            self._run_time_var.set(self._fmt(elapsed))
        elif not st["running"]:
            self._run_time_lbl.config(fg=FG)

        if st["running"]:
            self._pulse_state = not self._pulse_state
            col = GREEN if self._pulse_state else GREEN_A
            self._status_dot.itemconfig(self._dot_id, fill=col)

        if state._macro_thread and not state._macro_thread.is_alive():
            if self._status_var.get() in ("running", "stopping…"):
                self._start_btn.config(state="normal")
                self._stop_btn.config(state="disabled")
                self._set_status("idle", _DOT_IDLE)
                self._stopping = False

        if self._show_log.get():
            msgs = []
            try:
                while True:
                    msgs.append(self._log_queue.get_nowait())
            except queue.Empty:
                pass
            if msgs:
                self._log_text.config(state="normal")
                self._log_text.insert("end", "\n".join(msgs) + "\n")
                self._log_text.see("end")
                self._log_text.config(state="disabled")

        self.root.after(500, self._tick)

    # ── Close ─────────────────────────────────────────────────

    def _on_close(self):
        self._save()
        Main.stop()
        if state._macro_thread and state._macro_thread.is_alive():
            state._macro_thread.join(timeout=2.0)
        self.root.destroy()


# ── Single instance guard ─────────────────────────────────────

_MUTEX = None

def _acquire_single_instance():
    global _MUTEX
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, True, "CidAutoPlay_SingleInstance")
    return ctypes.windll.kernel32.GetLastError() != 183


def main():
    if not _acquire_single_instance():
        import tkinter.messagebox as mb
        _r = tk.Tk()
        _r.withdraw()
        mb.showerror(
            "Already running",
            "Cid Auto Play is already running.\n"
            "Open Task Manager → Details → find pythonw.exe → End Task.",
        )
        _r.destroy()
        sys.exit(1)

    root = tk.Tk()
    MacroGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
