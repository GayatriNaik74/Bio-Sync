"""
BioSync Phase 2 — User Enrollment
Fine-tunes the pre-trained model on a specific user's capture sessions.
Usage: python src/enrollment.py
"""

import os
import glob
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

# Add src/ to path so we can import features.py
import sys
sys.path.insert(0, 'src')
from features import load_events, compute_dwell, compute_flight, extract_features

# ── Paths ──────────────────────────────────────────
RAW_DIR      = "data/raw"
SCALER_PATH  = "models/pretrained_scaler.pkl"
BASELINE_OUT = "models/user_baseline.pkl"

# ── Step 1: Load all user sessions ─────────────────
def load_user_sessions():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "session_*.csv")))
    if not files:
        raise FileNotFoundError(f"No session CSVs found in {RAW_DIR}")
    print(f"  Found {len(files)} session files")
    return files

# ── Step 2: Extract features from each session ─────
def build_feature_matrix(files):
    feature_rows = []
    for path in files:
        try:
            df        = load_events(path)
            dwell_df  = compute_dwell(df)
            flight_df = compute_flight(df)

            if len(dwell_df) < 5 or len(flight_df) < 5:
                print(f"  ⚠ Skipping {path} — too few keystrokes")
                continue

            feat = extract_features(dwell_df, flight_df)
            feature_rows.append(list(feat.values()))
            print(f"  ✓ {os.path.basename(path)} → {len(dwell_df)} keypresses")
        except Exception as e:
            print(f"  ✗ Error processing {path}: {e}")

    if not feature_rows:
        raise ValueError("No valid sessions found for enrollment")

    return np.array(feature_rows)

# ── Step 3: Scale using CMU scaler ─────────────────
def scale_user_features(X):
    # Load the CMU-trained scaler for consistent feature scaling
    scaler = joblib.load(SCALER_PATH)
    n_cmu  = scaler.n_features_in_
    n_user = X.shape[1]

    # Pad or trim to match CMU feature count
    if n_user < n_cmu:
        pad   = np.zeros((X.shape[0], n_cmu - n_user))
        X_pad = np.hstack([X, pad])
    else:
        X_pad = X[:, :n_cmu]

    X_scaled = scaler.transform(X_pad)
    print(f"  Scaled user features to {n_cmu} dimensions")
    return X_scaled, scaler

# ── Step 4: Train personal Isolation Forest ─────────
def train_personal_model(X_scaled):
    print(f"  Training personal model on {len(X_scaled)} sessions...")
    model = IsolationForest(
    n_estimators=100,
    contamination=0.1,    # ← was 0.03, now 0.1
    random_state=42,
    n_jobs=-1)
    
    model.fit(X_scaled)
    scores = model.decision_function(X_scaled)
    print(f"  Personal score range: {scores.min():.4f} → {scores.max():.4f}")
    return model, scores

# ── Step 5: Build and save baseline profile ─────────
def save_baseline(model, scaler, scores, X_raw):
    baseline = {
        'model'       : model,
        'scaler'      : scaler,
        'mean_score'  : float(scores.mean()),
        'std_score'   : float(scores.std()),
        'threshold'   : float(scores.mean() - 2 * scores.std()),
        'n_sessions'  : X_raw.shape[0],
        # Store raw feature stats for Trust Score normalisation
        'feat_mean'   : X_raw.mean(axis=0).tolist(),
        'feat_std'    : X_raw.std(axis=0).tolist(),
    }
    os.makedirs("models", exist_ok=True)
    joblib.dump(baseline, BASELINE_OUT)
    print(f"\n  ✓ Baseline saved → {BASELINE_OUT}")
    print(f"  Trust threshold  : {baseline['threshold']:.4f}")
    print(f"  Sessions used    : {baseline['n_sessions']}")
    return baseline

# ── Main ────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 50)
    print("  BioSync — User Enrollment")
    print("═" * 50)

    files            = load_user_sessions()
    X_raw            = build_feature_matrix(files)
    X_scaled, scaler = scale_user_features(X_raw)
    model, scores    = train_personal_model(X_scaled)
    baseline         = save_baseline(model, scaler, scores, X_raw)

    print("\n  ✓ Enrollment complete!")
    print("  Next: run python src/trust_engine.py")