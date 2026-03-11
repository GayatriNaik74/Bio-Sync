"""
BioSync Phase 2 — Pre-training on CMU Keystroke Dataset
Trains Isolation Forest on 51 users to learn general human typing.
Run ONCE before any user enrolls:  python src/pretrain.py
"""

import os
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import joblib

# ── Paths ──────────────────────────────────────────
CMU_PATH    = "data/external/DSL-StrongPasswordData.csv"
MODEL_OUT   = "models/pretrained_iso_forest.pkl"
SCALER_OUT  = "models/pretrained_scaler.pkl"
FEATURE_OUT = "models/feature_names.pkl"

# ── Step 1: Load CMU dataset ────────────────────────
def load_cmu():
    if not os.path.exists(CMU_PATH):
        print(f"  ✗ CMU dataset not found at: {CMU_PATH}")
        print(f"  Download from: https://www.cs.cmu.edu/~keystroke/")
        raise FileNotFoundError(CMU_PATH)

    df = pd.read_csv(CMU_PATH)
    print(f"  Loaded  : {df.shape[0]} rows × {df.shape[1]} columns")
    print(f"  Subjects: {df['subject'].nunique()} unique users")
    print(f"  Sessions: {df.groupby('subject').size().mean():.0f} avg per user")
    return df

# ── Step 2: Extract feature matrix ─────────────────
def prepare_features(df):
    # Drop non-feature columns
    drop_cols = ['subject', 'sessionIndex', 'rep']
    feat_cols = [c for c in df.columns if c not in drop_cols]
    X = df[feat_cols].values

    # Remove rows with NaN values
    mask = ~np.isnan(X).any(axis=1)
    X = X[mask]
    print(f"  Features: {len(feat_cols)} columns")
    print(f"  Samples : {X.shape[0]} clean rows")
    return X, feat_cols

# ── Step 3: Scale features ──────────────────────────
def scale_features(X):
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"  Scaled  : mean≈0, std≈1 per feature")
    return X_scaled, scaler

# ── Step 4: Train Isolation Forest ─────────────────
def train_model(X_scaled):
    print(f"\n  Training Isolation Forest...")
    model = IsolationForest(
        n_estimators=300,      # 300 trees for better accuracy
        contamination=0.05,    # expect 5% anomalies
        max_samples='auto',
        random_state=42,
        n_jobs=-1              # use all CPU cores
    )
    model.fit(X_scaled)

    # Check scores on training data
    scores = model.decision_function(X_scaled)
    pct_normal = (model.predict(X_scaled) == 1).mean() * 100

    print(f"  Score range : {scores.min():.4f} → {scores.max():.4f}")
    print(f"  Avg score   : {scores.mean():.4f} ± {scores.std():.4f}")
    print(f"  % normal    : {pct_normal:.1f}%  (target ~95%)")
    return model, scores

# ── Step 5: Save everything ─────────────────────────
def save_all(model, scaler, feat_cols):
    os.makedirs("models", exist_ok=True)
    joblib.dump(model,     MODEL_OUT)
    joblib.dump(scaler,    SCALER_OUT)
    joblib.dump(feat_cols, FEATURE_OUT)
    print(f"\n  ✓ Model saved  → {MODEL_OUT}")
    print(f"  ✓ Scaler saved → {SCALER_OUT}")
    print(f"  ✓ Features saved → {FEATURE_OUT}")

# ── Main ────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 50)
    print("  BioSync — CMU Pre-training")
    print("═" * 50)

    df              = load_cmu()
    X, feat_cols    = prepare_features(df)
    X_scaled, scaler= scale_features(X)
    model, scores   = train_model(X_scaled)
    save_all(model, scaler, feat_cols)

    print("\n  ✓ Pre-training complete!")
    print("  Next: run python src/enrollment.py")