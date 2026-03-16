"""
BioSync Phase 2 — Trust Engine
Combines Isolation Forest score WITH direct feature
comparison against baseline for accurate detection.
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

# ── Model score → Trust 0-100 ────────────────────────
def score_to_trust(raw_score, baseline):
    mean  = baseline['mean_score']
    std   = baseline['std_score']
    z     = (raw_score - mean) / (std + 1e-9)
    trust = float(np.clip(85 + z * 10, 0, 100))
    return round(trust, 1)

# ── Risk level ───────────────────────────────────────
def get_risk_level(trust_score):
    if trust_score >= 55:
        return "LOW"
    elif trust_score >= 40:
        return "MEDIUM"
    else:
        return "HIGH"

# ── Direct feature comparison ────────────────────────
def _direct_compare(live_features: dict,
                    baseline: dict) -> float:
    """
    Directly compare live dwell/flight against
    baseline averages.
    Returns a trust score 0-100 based on how
    close the live typing is to the baseline.

    This catches intruders even when the IF model
    gives similar scores.
    """
    if ('feat_mean' not in baseline or
            'feat_std' not in baseline):
        return 85.0

    feat_mean = np.array(baseline['feat_mean'])
    feat_std  = np.array(baseline['feat_std']) + 1e-9

    # Key feature indices (from extract_features order):
    # 0  = dwell_mean
    # 1  = dwell_std
    # 7  = flight_mean
    # 8  = flight_std
    # 14 = dwell_flight_ratio
    # 15 = total_keypresses

    live_vals = list(live_features.values())
    n = min(len(live_vals), len(feat_mean))

    if n == 0:
        return 85.0

    live  = np.array(live_vals[:n])
    mean  = feat_mean[:n]
    std   = feat_std[:n]

    # Focus on most discriminative features only
    key_indices = [i for i in [0, 1, 7, 8, 14]
                   if i < n]

    if not key_indices:
        return 85.0

    # Z-score for each key feature
    z_scores = np.abs(
        (live[key_indices] - mean[key_indices]) /
        std[key_indices]
    )

    # Mean z-score across key features
    mean_z = float(np.mean(z_scores))

    # Convert to trust score:
    # mean_z = 0.0  → 90  (identical to baseline)
    # mean_z = 0.5  → 85  (very close)
    # mean_z = 1.0  → 80  (normal variation)
    # mean_z = 1.5  → 72  (borderline)
    # mean_z = 2.0  → 60  (suspicious)
    # mean_z = 3.0  → 36  (likely intruder)
    # mean_z = 4.0  → 12  (definite intruder)
    direct_trust = float(np.clip(
        90 - mean_z * 18, 0, 100))

    return round(direct_trust, 1)

# ── MAIN: score a window of events ───────────────────
def compute_trust_score(event_log: list,
                        baseline: dict) -> dict:

    # Empty buffer → user not typing → stay normal
    if not event_log:
        return {
            'score'      : 85.0,
            'risk'       : 'LOW',
            'raw_score'  : 0.0,
            'keystrokes' : 0
        }

    df = pd.DataFrame(event_log)
    if 'timestamp_ms' not in df.columns:
        return {
            'score'      : 85.0,
            'risk'       : 'LOW',
            'raw_score'  : 0.0,
            'keystrokes' : 0
        }

    dwell_df  = compute_dwell(df)
    flight_df = compute_flight(df)

    # Too few keystrokes → stay normal
    if len(dwell_df) < 3 or len(flight_df) < 3:
        return {
            'score'      : 85.0,
            'risk'       : 'LOW',
            'raw_score'  : 0.0,
            'keystrokes' : len(dwell_df)
        }

    features = extract_features(dwell_df, flight_df)
    X_raw    = np.array([list(features.values())])

    # Scale
    scaler = baseline['scaler']
    n_cmu  = scaler.n_features_in_
    n_user = X_raw.shape[1]
    if n_user < n_cmu:
        pad   = np.zeros((X_raw.shape[0],
                          n_cmu - n_user))
        X_pad = np.hstack([X_raw, pad])
    else:
        X_pad = X_raw[:, :n_cmu]
    X_scaled = scaler.transform(X_pad)

    # Score 1 — Isolation Forest
    model      = baseline['model']
    raw_score  = float(
        model.decision_function(X_scaled)[0])
    if_trust   = score_to_trust(raw_score, baseline)

    # Score 2 — Direct feature comparison
    direct_trust = _direct_compare(features, baseline)

    # Final — weighted combination
    # Direct comparison is more reliable for small datasets
    final = round(
        0.5 * if_trust + 0.5 * direct_trust, 1)
    final = float(np.clip(final, 0, 100))

    risk = get_risk_level(final)

    return {
        'score'      : final,
        'risk'       : risk,
        'raw_score'  : raw_score,
        'if_trust'   : if_trust,
        'direct'     : direct_trust,
        'keystrokes' : len(dwell_df),
    }


# ── Demo test ─────────────────────────────────────────
if __name__ == "__main__":
    import glob, csv

    print("=" * 50)
    print("  BioSync — Trust Engine Test")
    print("=" * 50)

    baseline = load_baseline()

    print("\n── Testing YOUR sessions ──")
    files = sorted(glob.glob("data/raw/session_*.csv"))
    if not files:
        print("  No session files found")
    else:
        for fpath in files:
            with open(fpath) as f:
                events = []
                for r in csv.DictReader(f):
                    evt = {
                        'timestamp_ms':
                            int(r['timestamp_ms']),
                        'key'        : r['key'],
                        'event_type' : r['event_type'],
                    }
                    if r.get('dwell_ms'):
                        evt['dwell_ms'] = float(
                            r['dwell_ms'])
                    if r.get('flight_ms'):
                        evt['flight_ms'] = float(
                            r['flight_ms'])
                    events.append(evt)

            r = compute_trust_score(events, baseline)
            print(f"  {os.path.basename(fpath)[-22:]}"
                  f" → final={r['score']}"
                  f" if={r['if_trust']}"
                  f" direct={r['direct']}"
                  f" risk={r['risk']}")

        print("\n── 30-second windows ──")
        with open(files[0]) as f:
            all_ev = []
            for r in csv.DictReader(f):
                evt = {
                    'timestamp_ms': int(r['timestamp_ms']),
                    'key'        : r['key'],
                    'event_type' : r['event_type'],
                }
                if r.get('dwell_ms'):
                    evt['dwell_ms'] = float(r['dwell_ms'])
                if r.get('flight_ms'):
                    evt['flight_ms'] = float(r['flight_ms'])
                all_ev.append(evt)

        for start in range(0, min(len(all_ev),120), 30):
            chunk = all_ev[start:start+30]
            r = compute_trust_score(chunk, baseline)
            print(f"  w{start:3d}-{start+30:3d}"
                  f" → final={r['score']}"
                  f" direct={r['direct']}"
                  f" risk={r['risk']}"
                  f" keys={r['keystrokes']}")

    print("\n── INTRUDER tests ──")

    tests = [
        ("Fast robot   ",
         [{'key':c,'dwell_ms':15,'flight_ms':10,
           'event_type':'press',
           'timestamp_ms':i*25}
          for i,c in enumerate(
              "the quick brown fox jumps over")]),
        ("Hunt-and-peck",
         [{'key':c,'dwell_ms':320,'flight_ms':480,
           'event_type':'press',
           'timestamp_ms':i*800}
          for i,c in enumerate(
              "the quick brown fox jumps over")]),
        ("Medium speed ",
         [{'key':c,'dwell_ms':190,'flight_ms':220,
           'event_type':'press',
           'timestamp_ms':i*410}
          for i,c in enumerate(
              "the quick brown fox jumps over")]),
    ]

    for label, evts in tests:
        r = compute_trust_score(evts, baseline)
        print(f"  {label}"
              f" → final={r['score']}"
              f" direct={r['direct']}"
              f" risk={r['risk']}")