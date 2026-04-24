import ctypes
import time

# ── Config ────────────────────────────────────────────────────────────────────
SCROLL_DOWN = 2    # clicks down (positive = down)
SCROLL_UP   = 1    # clicks up   (positive = up)
DELAY       = 1.5  # seconds between down and up
# ─────────────────────────────────────────────────────────────────────────────

def scroll(clicks):
    """Positive = down, negative = up. One click = one notch."""
    ctypes.windll.user32.mouse_event(0x0800, 0, 0, -120 * clicks, 0)

print(f"Scrolling DOWN {SCROLL_DOWN} clicks in 3s...")
time.sleep(3)
scroll(SCROLL_DOWN)
print(f"Done. Waiting {DELAY}s...")
