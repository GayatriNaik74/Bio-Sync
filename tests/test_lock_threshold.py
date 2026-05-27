import sys
sys.path.insert(0, 'src')
from lock_manager import should_lock, LOCK_THRESHOLD

print(f"  Lock threshold: {LOCK_THRESHOLD}")

cases = [
    (45.0, False),   # at threshold — should NOT lock
    (44.9, True),    # just below — should lock
    (0.0,  True),    # minimum — should lock
    (100.0, False),  # maximum — should NOT lock
]

for score, expected in cases:
    got = should_lock(score)
    status = "✓" if got == expected else "✗"
    print(f"  {status}  score={score:5.1f}  "
          f"locks={got}  expected={expected}")
    assert got == expected

print("\n✓ Lock threshold: PASS")