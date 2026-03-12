"""
BioSync Phase 3 — Lock Manager
Locks the OS session when trust score drops below threshold.
Called by trust_engine.py when risk level is HIGH.
"""

import sys
import os
import subprocess
import datetime

LOCK_THRESHOLD = 60   # lock if score drops below this
LOCK_LOG       = "data/processed/lock_events.txt"

def lock_workstation(reason: str = "Trust score below threshold"):
    """Lock the OS session immediately."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  🔒 LOCKING SESSION — {reason}")

    # Log the lock event to file
    os.makedirs("data/processed", exist_ok=True)
    with open(LOCK_LOG, 'a') as f:
        f.write(f"{timestamp} | LOCK | {reason}\n")

    # Platform-specific lock
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.LockWorkStation()

    elif sys.platform == 'darwin':   # Mac
        subprocess.run([
            'osascript', '-e',
            'tell application "System Events" to keystroke "q" using {control down, command down}'
        ])

    else:                              # Linux
        subprocess.run(['gnome-screensaver-command', '--lock'])

def should_lock(trust_score: float) -> bool:
    """Returns True if the score is low enough to trigger a lock."""
    return trust_score < LOCK_THRESHOLD

def log_restore(session_id: str):
    """Log that a session was successfully restored after re-auth."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs("data/processed", exist_ok=True)
    with open(LOCK_LOG, 'a') as f:
        f.write(f"{timestamp} | RESTORE | {session_id}\n")
    print(f"  ✓ Session restored — logged to {LOCK_LOG}")

# ── Demo test ────────────────────────────────────────
if __name__ == "__main__":
    print("  Lock threshold :", LOCK_THRESHOLD)
    print("  Score 85  → lock?", should_lock(85))   # False
    print("  Score 45  → lock?", should_lock(45))   # True
    print("  Score 59  → lock?", should_lock(59))   # True
    print("  (Not actually locking — demo only)")