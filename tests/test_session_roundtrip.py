import sys, os, csv, time
sys.path.insert(0, 'src')
from features import load_events, compute_dwell, compute_flight, extract_features

# Build synthetic session data
RAW_DIR = "data/raw"
os.makedirs(RAW_DIR, exist_ok=True)
test_path = os.path.join(RAW_DIR, "session_TEST.csv")

events = []
t = 1700000000000
for i, ch in enumerate("the quick brown fox jumps over"):
    events.append({
        'timestamp_ms': t,
        'key':          ch,
        'event_type':  'press',
        'dwell_ms':    120,
        'flight_ms':   150 if i > 0 else 0,
    })
    t += 270

# Save CSV
with open(test_path, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=[
        'timestamp_ms','key','event_type',
        'dwell_ms','flight_ms'])
    w.writeheader()
    w.writerows(events)
print(f"✓ Session CSV written: {len(events)} rows")

# Reload and extract
df        = load_events(test_path)
dwell_df  = compute_dwell(df)
flight_df = compute_flight(df)
assert len(dwell_df)  > 5, f"Too few dwell rows: {len(dwell_df)}"
assert len(flight_df) > 5, f"Too few flight rows: {len(flight_df)}"
print(f"✓ Dwell rows: {len(dwell_df)}")
print(f"✓ Flight rows: {len(flight_df)}")

features = extract_features(dwell_df, flight_df)
assert 'dwell_mean'   in features
assert 'flight_mean'  in features
assert features['dwell_mean'] > 0
assert features['flight_mean'] > 0
print(f"  dwell_mean  = {features['dwell_mean']:.1f} ms")
print(f"  flight_mean = {features['flight_mean']:.1f} ms")

# Cleanup
os.remove(test_path)
print(f"✓ Test CSV cleaned up")
print("\n✓ Session round-trip: PASS")