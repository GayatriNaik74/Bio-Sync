"""
BioSync Phase 2 — Trust Engine
Combines Isolation Forest + direct feature comparison.
Now includes digraph and trigraph timing features.
"""

import os
import numpy as np
import joblib
import sys
sys.path.insert(0, 'src')
from features import (compute_dwell, compute_flight,
                      extract_features)
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
    Compare live features against baseline averages.
    Now includes digraph/trigraph features when available.
    """
    if ('feat_mean' not in baseline or
            'feat_std' not in baseline):
        return 85.0

    feat_mean = np.array(baseline['feat_mean'])
    feat_std  = np.array(baseline['feat_std']) + 1e-9

    live_vals = list(live_features.values())
    n = min(len(live_vals), len(feat_mean))
    if n == 0:
        return 85.0

    live = np.array(live_vals[:n])
    mean = feat_mean[:n]
    std  = feat_std[:n]

    # Core indices — dwell_mean(0), dwell_std(1),
    # flight_mean(7), flight_std(8), ratio(14)
    key_indices = [i for i in [0, 1, 7, 8, 14]
                   if i < n]

    # Add digraph overall mean index if present
    feat_names = list(live_features.keys())
    for extra in ['dg_overall_mean',
                  'dg_overall_std',
                  'tg_overall_mean']:
        if extra in feat_names:
            idx = feat_names.index(extra)
            if idx < n and idx not in key_indices:
                key_indices.append(idx)

    if not key_indices:
        return 85.0

    z_scores = np.abs(
        (live[key_indices] - mean[key_indices]) /
        std[key_indices]
    )
    mean_z = float(np.mean(z_scores))

    direct_trust = float(np.clip(
        90 - mean_z * 18, 0, 100))
    return round(direct_trust, 1)

# ── MAIN: score a window of events ───────────────────
def compute_trust_score(event_log: list,
                        baseline: dict) -> dict:

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

    if len(dwell_df) < 3 or len(flight_df) < 3:
        return {
            'score'      : 85.0,
            'risk'       : 'LOW',
            'raw_score'  : 0.0,
            'keystrokes' : len(dwell_df)
        }

    # Extract features WITH digraph/trigraph
    features = extract_features(
        dwell_df, flight_df, df_raw=df)
    X_raw    = np.array([list(features.values())])

    # Scale — handle dimension mismatch gracefully
    scaler = baseline['scaler']
    n_cmu  = scaler.n_features_in_
    n_user = X_raw.shape[1]
    if n_user < n_cmu:
        pad   = np.zeros((X_raw.shape[0],
                          n_cmu - n_user))
        X_pad = np.hstack([X_raw, pad])
    elif n_user > n_cmu:
        X_pad = X_raw[:, :n_cmu]
    else:
        X_pad = X_raw
    X_scaled = scaler.transform(X_pad)

    # Isolation Forest score
    model     = baseline['model']
    raw_score = float(
        model.decision_function(X_scaled)[0])
    if_trust  = score_to_trust(raw_score, baseline)

    # Direct feature comparison
    direct_trust = _direct_compare(
        features, baseline)

    # Combined score
    final = round(
        0.5 * if_trust + 0.5 * direct_trust, 1)
    final = float(np.clip(final, 0, 100))
    risk  = get_risk_level(final)

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
                  f" if={r.get('if_trust','?')}"
                  f" direct={r.get('direct','?')}"
                  f" risk={r['risk']}")

        print("\n── 30-second windows ──")
        with open(files[0]) as f:
            all_ev = []
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
                all_ev.append(evt)

        for start in range(
                0, min(len(all_ev), 120), 30):
            chunk = all_ev[start:start+30]
            r = compute_trust_score(chunk, baseline)
            print(f"  w{start:3d}-{start+30:3d}"
                  f" → final={r['score']}"
                  f" direct={r.get('direct','?')}"
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
              f" direct={r.get('direct','?')}"
              f" risk={r['risk']}")