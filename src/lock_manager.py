"""
BioSync — Lock Manager
Instant lock when trust score drops below threshold.
"""
import ctypes

LOCK_THRESHOLD = 45

def should_lock(trust_score: float) -> bool:
    return float(trust_score) < LOCK_THRESHOLD

def reset_lock_counter():
    pass

def lock_workstation():
    try:
        ctypes.windll.user32.LockWorkStation()
    except Exception:
        pass