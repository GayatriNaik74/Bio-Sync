"""Run all BioSync unit tests in sequence."""
import subprocess, sys

tests = [
    ("Risk Levels",      "tests/test_risk_levels.py"),
    ("Lock Threshold",   "tests/test_lock_threshold.py"),
    ("Admin Auth",       "tests/test_admin_auth.py"),
    ("Admin Logger",     "tests/test_admin_logger.py"),
    ("Session Roundtrip","tests/test_session_roundtrip.py"),
    ("Trust Score",      "tests/test_trust_score.py"),
]

passed = []
failed = []

for name, path in tests:
    print(f"\n{'─'*40}")
    print(f"  Running: {name}")
    print(f"{'─'*40}")
    result = subprocess.run(
        [sys.executable, path],
        capture_output=False)
    if result.returncode == 0:
        passed.append(name)
    else:
        failed.append(name)

print(f"\n{'═'*40}")
print(f"  RESULTS:  {len(passed)} passed  /  {len(failed)} failed")
print(f"{'═'*40}")
for t in passed: print(f"  ✓  {t}")
for t in failed: print(f"  ✗  {t}")