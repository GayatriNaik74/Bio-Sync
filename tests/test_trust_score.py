import sys
sys.path.insert(0, 'src')
from trust_engine import compute_trust_score, load_baseline

baseline = load_baseline()

# TEST A: Empty event list → safe default
result = compute_trust_score([], baseline)
assert result['score']      == 85.0, "Empty should return 85"
assert result['risk']       == 'LOW'
assert result['keystrokes'] == 0
print("✓ Empty events → score=85.0 LOW")

# TEST B: Too few events (< 3 dwell+flight)
tiny = [
    {'timestamp_ms': i*200, 'key': 'a',
     'event_type': 'press', 'dwell_ms': 100}
    for i in range(2)
]
result = compute_trust_score(tiny, baseline)
assert result['score'] == 85.0
print("✓ Too few events → score=85.0 LOW (safe default)")

# TEST C: Realistic fast-robot intruder → HIGH risk
robot = [
    {'timestamp_ms': i*25, 'key': c,
     'event_type': 'press',
     'dwell_ms': 12, 'flight_ms': 13}
    for i, c in enumerate("the quick brown fox jumps")
]
result = compute_trust_score(robot, baseline)
print(f"  Robot score: {result['score']}  risk: {result['risk']}")
assert result['score'] < 60, \
    f"Robot should score < 60, got {result['score']}"
print("✓ Robot intruder → score < 60")

# TEST D: Result dict has all required keys
required = ['score','risk','raw_score','keystrokes']
for k in required:
    assert k in result, f"Missing key: {k}"
print("✓ Result dict has all required keys")

print("\n✓ compute_trust_score: PASS")