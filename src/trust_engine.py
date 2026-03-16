"""
BioSync Phase 2 — Trust Engine
Converts live keystroke data into a Trust Score (0-100).
"""

import os
import numpy as np
import joblib
import sys
sys.path.insert(0, 'src')
from features import compute_dwell, compute_flight, extract_features
import pandas as pd

BASELINE_PATH = "models/user_baseline.pkl"

# ── Load baseline ────────────────────────────────────
def load_baseline():
    if not os.path.exists(BASELINE_PATH):
        raise FileNotFoundError(
            "No baseline found. Run enrollment first.")
    baseline = joblib.load(BASELINE_PATH)
    print(f"  ✓ Baseline loaded")
    print(f"  Mean score : {baseline['mean_score']:.4f}")
    print(f"  Std score  : {baseline['std_score']:.4f}")
    print(f"  Threshold  : {baseline['threshold']:.4f}")
    return baseline

# ── Score → Trust 0-100 ──────────────────────────────
def score_to_trust(raw_score, baseline):
    mean = baseline['mean_score']
    std  = baseline['std_score']

    # Normalise: how many std devs from mean
    z = (raw_score - mean) / (std + 1e-9)

    # Map z-score to trust
    # z >= +1  → 95+  (very normal typing)
    # z =   0  → 85   (normal)
    # z =  -1  → 72   (slight variation)
    # z =  -2  → 59   (MEDIUM — suspicious)
    # z =  -3  → 46   (HIGH — likely intruder)
    # z =  -4  → 33   (definite intruder)
    trust = float(np.clip(85 + z * 13, 0, 100))
    return round(trust, 1)

# ── Risk level from trust score ──────────────────────
def get_risk_level(trust_score):
    if trust_score >= 72:
        return "LOW"
    elif trust_score >= 55:
        return "MEDIUM"
    else:
        return "HIGH"

# ── Feature distance scoring ─────────────────────────
def _feature_distance_score(X_raw, baseline):
    """
    Compare live features against baseline feat_mean.
    Returns a penalty score 0-100 (higher = more different).
    """
    if 'feat_mean' not in baseline or 'feat_std' not in baseline:
        return 0.0

    feat_mean = np.array(baseline['feat_mean'])
    feat_std  = np.array(baseline['feat_std']) + 1e-9

    n = min(X_raw.shape[1], len(feat_mean))
    live    = X_raw[0, :n]
    mean    = feat_mean[:n]
    std     = feat_std[:n]

    # Z-score each feature
    z_scores = np.abs((live - mean) / std)

    # Key features: dwell_mean(0), flight_mean(7)
    # Weight them more heavily
    weights = np.ones(n)
    if n > 0:  weights[0] = 3.0   # dwell_mean
    if n > 1:  weights[1] = 2.0   # dwell_std
    if n > 7:  weights[7] = 3.0   # flight_mean
    if n > 8:  weights[8] = 2.0   # flight_std
    if n > 14: weights[14] = 2.0  # dwell_flight_ratio

    weighted_z = np.average(z_scores, weights=weights[:n])
    return float(weighted_z)

# ── MAIN: score a window of events ───────────────────
def compute_trust_score(event_log: list,
                        baseline: dict) -> dict:
    # Empty buffer → assume normal (user not typing)
    if not event_log:
        return {
            'score'       : 85.0,
            'risk'        : 'LOW',
            'raw_score'   : 0.0,
            'top_features': [],
            'keystrokes'  : 0
        }

    # Build DataFrame
    df = pd.DataFrame(event_log)
    if 'timestamp_ms' not in df.columns:
        return {
            'score'       : 85.0,
            'risk'        : 'LOW',
            'raw_score'   : 0.0,
            'top_features': [],
            'keystrokes'  : 0
        }

    dwell_df  = compute_dwell(df)
    flight_df = compute_flight(df)

    # Too few keystrokes — don't penalise
    if len(dwell_df) < 3:
        return {
            'score'       : 85.0,
            'risk'        : 'LOW',
            'raw_score'   : 0.0,
            'top_features': [],
            'keystrokes'  : len(dwell_df)
        }

    features = extract_features(dwell_df, flight_df)
    X_raw    = np.array([list(features.values())])

    # Scale
    scaler = baseline['scaler']
    n_cmu  = scaler.n_features_in_
    n_user = X_raw.shape[1]
    if n_user < n_cmu:
        pad   = np.zeros((X_raw.shape[0], n_cmu - n_user))
        X_pad = np.hstack([X_raw, pad])
    else:
        X_pad = X_raw[:, :n_cmu]
    X_scaled = scaler.transform(X_pad)

    # Model score
    model     = baseline['model']
    raw_score = float(model.decision_function(X_scaled)[0])

    # Feature distance score (direct comparison to baseline)
    feat_dist = _feature_distance_score(X_raw, baseline)

    # Combine model score with feature distance
    # If features are very different → penalise more
    model_trust = score_to_trust(raw_score, baseline)

    # Feature distance penalty
    # feat_dist = 0   → no penalty
    # feat_dist = 1   → small penalty (-5)
    # feat_dist = 2   → medium penalty (-15)
    # feat_dist = 3+  → large penalty (-30+)
    penalty = min(40, float(feat_dist) * 12)
    combined_trust = float(np.clip(model_trust - penalty, 0, 100))

    # Final risk
    risk = get_risk_level(combined_trust)

    return {
        'score'       : round(combined_trust, 1),
        'risk'        : risk,
        'raw_score'   : raw_score,
        'top_features': [],
        'keystrokes'  : len(dwell_df),
        'feat_dist'   : round(feat_dist, 3),
    }

# ── Demo test ─────────────────────────────────────────
if __name__ == "__main__":
    import glob, csv

    print("=" * 50)
    print("  BioSync — Trust Engine Test")
    print("=" * 50)

    baseline = load_baseline()

    print("\n── Testing with YOUR typing pattern ──")
    files = sorted(glob.glob("data/raw/session_*.csv"))
    if files:
        with open(files[0]) as f:
            reader = csv.DictReader(f)
            events = []
            for r in reader:
                evt = {
                    'timestamp_ms': int(r['timestamp_ms']),
                    'key'         : r['key'],
                    'event_type'  : r['event_type'],
                }
                if r.get('dwell_ms'):
                    evt['dwell_ms']  = float(r['dwell_ms'])
                if r.get('flight_ms'):
                    evt['flight_ms'] = float(r['flight_ms'])
                events.append(evt)

        result = compute_trust_score(events, baseline)
        print(f"  Trust Score  : {result['score']}")
        print(f"  Risk Level   : {result['risk']}")
        print(f"  Raw Score    : {result['raw_score']:.4f}")
        print(f"  Feat Distance: {result.get('feat_dist', 'N/A')}")
        print(f"  Keypresses   : {result['keystrokes']}")

    print("\n── Testing with INTRUDER (fast robotic typing) ──")
    intruder = [
        {'key': c, 'dwell_ms': 18, 'flight_ms': 12,
         'event_type': 'press',
         'timestamp_ms': i * 30}
        for i, c in enumerate("authentication systems verify user identity")
    ]
    r2 = compute_trust_score(intruder, baseline)
    print(f"  Trust Score  : {r2['score']}")
    print(f"  Risk Level   : {r2['risk']}")
    print(f"  Feat Distance: {r2.get('feat_dist', 'N/A')}")

    print("\n── Testing with INTRUDER (slow hunt-and-peck) ──")
    intruder2 = [
        {'key': c, 'dwell_ms': 280, 'flight_ms': 450,
         'event_type': 'press',
         'timestamp_ms': i * 730}
        for i, c in enumerate("authentication systems verify user identity")
    ]
    r3 = compute_trust_score(intruder2, baseline)
    print(f"  Trust Score  : {r3['score']}")
    print(f"  Risk Level   : {r3['risk']}")
    print(f"  Feat Distance: {r3.get('feat_dist', 'N/A')}")