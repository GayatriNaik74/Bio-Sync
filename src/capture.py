"""
BioSync Phase 1 — Keystroke Capture
Records keyboard events to a CSV file.
Run: python src/capture.py
Stop: Press ESC key
"""

import csv
import os
import time
import datetime
from pynput import keyboard

# ── Configuration ──────────────────────────────────
OUTPUT_DIR  = "data/raw"
SESSION_ID  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"session_{SESSION_ID}.csv")

# ── State ──────────────────────────────────────────
event_log    = []
start_time   = None
press_times  = {}   # tracks when each key was pressed

# ── Helpers ────────────────────────────────────────
def get_ms():
    """Return current time in milliseconds."""
    return int(time.time() * 1000)

def key_name(key):
    """Convert pynput key object to a clean string."""
    try:
        return key.char if key.char else str(key)
    except AttributeError:
        return str(key)

# ── Event Handlers ─────────────────────────────────
def on_press(key):
    global start_time
    now = get_ms()

    # Record the start time on first keypress
    if start_time is None:
        start_time = now
        print(f"  Recording started. Press ESC to stop and save.")

    name = key_name(key)
    press_times[name] = now

    event_log.append({
        'timestamp_ms': now,
        'elapsed_ms'  : now - start_time,
        'key'         : name,
        'event_type'  : 'press',
        'dwell_ms'    : '',     # filled in on release
        'flight_ms'   : ''      # filled in on next press
    })

def on_release(key):
    now  = get_ms()
    name = key_name(key)

    # Calculate dwell time (how long the key was held down)
    dwell = now - press_times.get(name, now)

    event_log.append({
        'timestamp_ms': now,
        'elapsed_ms'  : now - (start_time or now),
        'key'         : name,
        'event_type'  : 'release',
        'dwell_ms'    : dwell,
        'flight_ms'   : ''
    })

    # Stop recording when ESC is pressed
    if key == keyboard.Key.esc:
        save_to_csv()
        return False  # returning False stops the listener

# ── Save ───────────────────────────────────────────
def save_to_csv():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fieldnames = ['timestamp_ms', 'elapsed_ms', 'key',
                  'event_type', 'dwell_ms', 'flight_ms']

    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(event_log)

    print(f"\n✓ Saved {len(event_log)} events → {OUTPUT_FILE}")
    print(f"  Session duration: {event_log[-1]['elapsed_ms']/1000:.1f}s")
    print(f"  Total key events: {len(event_log)}")

# ── Main ───────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 48)
    print("  BioSync — Keystroke Capture")
    print(f"  Output: {OUTPUT_FILE}")
    print("═" * 48)
    print("  Start typing. Press ESC to stop.")
    print()

    with keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    ) as listener:
        listener.join()
