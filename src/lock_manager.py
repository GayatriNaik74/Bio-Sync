"""
BioSync — Lock Manager
Decides when to lock the session based on trust score.
"""

import ctypes
import os

# Lock when trust score drops below this
LOCK_THRESHOLD = 50

# How many consecutive HIGH readings before locking
# Prevents single-window false positives
CONSECUTIVE_REQUIRED = 2

_consecutive_high = 0

def should_lock(trust_score: float) -> bool:
    """
    Returns True if session should be locked.
    Requires CONSECUTIVE_REQUIRED consecutive HIGH scores
    to avoid false positives from single bad windows.
    """
    global _consecutive_high

    if trust_score < LOCK_THRESHOLD:
        _consecutive_high += 1
    else:
        _consecutive_high = 0   # reset on normal score

    if _consecutive_high >= CONSECUTIVE_REQUIRED:
        _consecutive_high = 0   # reset after triggering
        return True

    return False

def reset_lock_counter():
    """Call this when session is restored after re-auth."""
    global _consecutive_high
    _consecutive_high = 0

def lock_workstation():
    """Lock Windows workstation."""
    try:
        ctypes.windll.user32.LockWorkStation()
    except Exception:
        pass