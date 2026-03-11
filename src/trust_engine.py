"""
BioSync Phase 2 — Trust Engine
Converts live keystroke data into a Trust Score (0–100).
Called every 5 seconds by the dashboard.
Usage: python src/trust_engine.py  (runs a demo test)
"""

import os
import numpy as np
import joblib
import shap

import sys
sys.path.insert(0, 'src')
from features import compute_dwell, compute_flight, extract_features
import pandas as pd

BASELINE_PATH = "models/user_baseline.pkl"

# ── Load baseline once at startup ───────────────────
def load_baseline():
    if not os.path.exists(BASELINE_PATH):
        raise FileNotFoundError("No baseline found. Run enrollment.py first.")
    baseline = joblib.load(BASELINE_PATH)
    print(f"  ✓ Baseline loaded")
    print(f"  Mean score : {baseline['mean_score']:.4f}")
    print(f"  Std score  : {baseline['std_score']:.4f}")
    print(f"  Threshold  : {baseline['threshold']:.4f}")
    return baseline

# ── Map raw anomaly score → Trust Score 0–100 ───────
def score_to_trust(raw_score, baseline):
    mean      = baseline['mean_score']
    std       = baseline['std_score']

    # How far is this score from the mean, relative to std?
    z = (raw_score - mean) / (std + 1e-9)

    # Map z to 0-100 with gentler scaling
    # z = 0  (at mean)       → 85
    # z = +1 (above mean)    → 95
    # z = -1 (below mean)    → 75
    # z = -3 (3 std below)   → 55 (warning zone)
    # z = -5 (very anomalous)→ 35 (lock zone)
    trust = float(np.clip(85 + z * 10, 0, 100))
    return round(trust, 1)

# ── Determine risk level from trust score ───────────
def get_risk_level(trust_score):
    if trust_score >= 80:
        return "LOW"       # green — safe
    elif trust_score >= 60:
        return "MEDIUM"    # amber — soft warning
    else:
        return "HIGH"      # red — trigger lock

# ── Compute SHAP explanation ─────────────────────────
def get_shap_values(model, X_scaled, feat_names):
    try:
        explainer   = shap.Explainer(model, X_scaled)
        shap_vals   = explainer(X_scaled)
        importance  = np.abs(shap_vals.values[0])
        top_idx     = importance.argsort()[::-1][:5]
        top_features = [
            {'feature': feat_names[i], 'importance': float(importance[i])}
            for i in top_idx
        ]
        return top_features
    except Exception:
        # SHAP can fail on very small inputs — return empty
        return []

# ── MAIN FUNCTION: score a window of events ──────────
def compute_trust_score(event_log: list, baseline: dict) -> dict:
    """
    Takes a list of keystroke event dicts (from capture.py format)
    and returns a trust score result.

    event_log: list of dicts with keys:
        timestamp_ms, key, event_type
    baseline: loaded from models/user_baseline.pkl

    Returns dict:
        score      — float 0–100
        risk       — 'LOW' / 'MEDIUM' / 'HIGH'
        raw_score  — raw Isolation Forest score
        top_features — list of top SHAP contributors
        keystrokes — number of keypresses in window
    """
    if not event_log:
        return {'score': 50.0, 'risk': 'MEDIUM',
                'raw_score': 0.0, 'top_features': [], 'keystrokes': 0}

    # Convert to DataFrame matching capture.py output format
    df = pd.DataFrame(event_log)
    if 'timestamp_ms' not in df.columns:
        return {'score': 50.0, 'risk': 'MEDIUM',
                'raw_score': 0.0, 'top_features': [], 'keystrokes': 0}

    dwell_df  = compute_dwell(df)
    flight_df = compute_flight(df)

    if len(dwell_df) < 5:
        return {'score': 75.0, 'risk': 'LOW',
                'raw_score': 0.0, 'top_features': [], 'keystrokes': len(dwell_df)}

    features  = extract_features(dwell_df, flight_df)
    X_raw     = np.array([list(features.values())])

    # Scale to match CMU dimensions
    scaler = baseline['scaler']
    n_cmu  = scaler.n_features_in_
    n_user = X_raw.shape[1]
    if n_user < n_cmu:
        pad   = np.zeros((X_raw.shape[0], n_cmu - n_user))
        X_pad = np.hstack([X_raw, pad])
    else:
        X_pad = X_raw[:, :n_cmu]
    X_scaled = scaler.transform(X_pad)

    # Get raw anomaly score
    model     = baseline['model']
    raw_score = float(model.decision_function(X_scaled)[0])
    trust     = score_to_trust(raw_score, baseline)
    risk      = get_risk_level(trust)

    # SHAP feature importance
    feat_names   = list(features.keys())
    top_features = get_shap_values(model, X_scaled, feat_names)

    return {
        'score'       : trust,
        'risk'        : risk,
        'raw_score'   : raw_score,
        'top_features': top_features,
        'keystrokes'  : len(dwell_df),
    }

# ── Demo test ────────────────────────────────────────
if __name__ == "__main__":
    import glob, csv

    print("═" * 50)
    print("  BioSync — Trust Engine Test")
    print("═" * 50)

    baseline = load_baseline()

    # Load a real session to test with
    files = sorted(glob.glob("data/raw/session_*.csv"))
    if not files:
        print("  No session files found")
    else:
        with open(files[0]) as f:
            reader = csv.DictReader(f)
            events = [{'timestamp_ms': int(r['timestamp_ms']),
                       'key': r['key'],
                       'event_type': r['event_type']}
                      for r in reader]

        result = compute_trust_score(events, baseline)

        print(f"\n  Trust Score  : {result['score']}")
        print(f"  Risk Level   : {result['risk']}")
        print(f"  Raw Score    : {result['raw_score']:.4f}")
        print(f"  Keypresses   : {result['keystrokes']}")
        if result['top_features']:
            print(f"\n  Top contributing features:")
            for feat in result['top_features']:
                print(f"    {feat['feature']:25s} {feat['importance']:.4f}")