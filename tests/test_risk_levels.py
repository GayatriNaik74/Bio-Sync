import sys
sys.path.insert(0, 'src')
from trust_engine import get_risk_level

cases = [
    (100.0, "LOW"),
    (55.0,  "LOW"),    # exact boundary
    (54.9,  "MEDIUM"), # just below LOW
    (40.0,  "MEDIUM"), # exact boundary
    (39.9,  "HIGH"),   # just below MEDIUM
    (0.0,   "HIGH"),
]

for score, expected in cases:
    got = get_risk_level(score)
    status = "✓" if got == expected else "✗"
    print(f"  {status}  score={score:5.1f}  "
          f"expected={expected:6s}  got={got}")
    assert got == expected, f"FAIL at score={score}"

print("\n✓ Risk levels: PASS")