"""
BioSync Phase 1 — Feature Extraction
Reads raw keystroke CSV and computes dwell/flight features.
Usage: python src/features.py data/raw/session_XXXX.csv

NOTE: CSVs saved by ui/enrollment.py already contain
      pre-calculated dwell_ms and flight_ms columns.
      This version reads those directly instead of
      computing from press/release pairs.
"""

import sys
import csv
import os
import json
import numpy as np
import pandas as pd

# ── Load raw events ──────────────────────────────────
def load_events(filepath):
    """Load a raw capture CSV into a pandas DataFrame."""
    df = pd.read_csv(filepath)
    print(f"  Loaded {len(df)} events from {filepath}")
    return df

# ── Compute dwell times ──────────────────────────────
def compute_dwell(df):
    """
    Read pre-calculated dwell_ms from CSV.
    Filters out zero/noise values.
    Returns DataFrame with columns: key, dwell_ms
    """
    # Use pre-calculated dwell_ms column directly
    if 'dwell_ms' in df.columns:
        dwell_df = df[['key', 'dwell_ms']].copy()
        # Filter: keep only valid dwell times (10ms–2000ms)
        dwell_df = dwell_df[
            (dwell_df['dwell_ms'] > 10) &
            (dwell_df['dwell_ms'] < 2000)
        ].reset_index(drop=True)
        return dwell_df

    # Fallback: compute from press/release pairs (old format)
    dwells    = []
    press_map = {}

    for _, row in df.iterrows():
        key = row['key']
        ts  = row['timestamp_ms']

        if row['event_type'] == 'press':
            press_map[key] = ts
        elif row['event_type'] == 'release' and key in press_map:
            dwell = ts - press_map[key]
            if 10 < dwell < 2000:
                dwells.append({'key': key, 'dwell_ms': dwell})
            del press_map[key]

    return pd.DataFrame(dwells)

# ── Compute flight times ─────────────────────────────
def compute_flight(df):
    """
    Read pre-calculated flight_ms from CSV.
    Filters out zero/noise values.
    Returns DataFrame with columns: from_key, to_key, flight_ms
    """
    # Use pre-calculated flight_ms column directly
    if 'flight_ms' in df.columns:
        flight_df = df[['key', 'flight_ms']].copy()
        # Filter: keep valid flight times (1ms–2000ms)
        flight_df = flight_df[
            (flight_df['flight_ms'] > 1) &
            (flight_df['flight_ms'] < 2000)
        ].reset_index(drop=True)
        # Rename for compatibility
        flight_df = flight_df.rename(columns={'key': 'to_key'})
        flight_df['from_key'] = flight_df['to_key'].shift(1).fillna('')
        return flight_df

    # Fallback: compute from press/release pairs (old format)
    flights          = []
    last_release_time = None
    last_release_key  = None

    for _, row in df.iterrows():
        ts  = row['timestamp_ms']
        key = row['key']

        if row['event_type'] == 'release':
            last_release_time = ts
            last_release_key  = key
        elif row['event_type'] == 'press' and last_release_time:
            flight = ts - last_release_time
            if 0 < flight < 2000:
                flights.append({
                    'from_key'  : last_release_key,
                    'to_key'    : key,
                    'flight_ms' : flight
                })

    return pd.DataFrame(flights)

# ── Summarise into one feature vector ────────────────
def extract_features(dwell_df, flight_df):
    """
    Compute statistical summary features from dwell and flight data.
    This becomes one row in the training dataset.
    """
    d = dwell_df['dwell_ms'].values
    f = flight_df['flight_ms'].values

    # Safety: pad with zeros if too short
    if len(d) == 0:
        d = np.array([100.0])
    if len(f) == 0:
        f = np.array([100.0])

    features = {
        # Dwell time statistics
        'dwell_mean'   : float(np.mean(d)),
        'dwell_std'    : float(np.std(d)),
        'dwell_min'    : float(np.min(d)),
        'dwell_max'    : float(np.max(d)),
        'dwell_median' : float(np.median(d)),
        'dwell_p25'    : float(np.percentile(d, 25)),
        'dwell_p75'    : float(np.percentile(d, 75)),

        # Flight time statistics
        'flight_mean'  : float(np.mean(f)),
        'flight_std'   : float(np.std(f)),
        'flight_min'   : float(np.min(f)),
        'flight_max'   : float(np.max(f)),
        'flight_median': float(np.median(f)),
        'flight_p25'   : float(np.percentile(f, 25)),
        'flight_p75'   : float(np.percentile(f, 75)),

        # Derived / ratio features
        'dwell_flight_ratio': float(np.mean(d) / (np.mean(f) + 1)),
        'total_keypresses'  : int(len(d)),
    }

    return features

# ── Print summary ─────────────────────────────────────
def print_summary(features):
    print()
    print("=" * 48)
    print("  Feature Summary")
    print("=" * 48)
    print(f"  Avg dwell time  : {features['dwell_mean']:.1f} ms")
    print(f"  Avg flight time : {features['flight_mean']:.1f} ms")
    print(f"  Dwell std dev   : {features['dwell_std']:.1f} ms")
    print(f"  Total keypresses: {features['total_keypresses']}")
    print()

# ── Save processed features ───────────────────────────
def save_features(features, source_file):
    out_dir  = "data/processed"
    basename = os.path.splitext(os.path.basename(source_file))[0]
    out_path = os.path.join(out_dir, f"{basename}_features.json")

    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({k: float(v) for k, v in features.items()}, f, indent=2)

    print(f"  ✓ Features saved → {out_path}")
    return out_path

# ── Main ──────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/features.py data/raw/session_XXX.csv")
        sys.exit(1)

    filepath  = sys.argv[1]
    print(f"\n  Processing: {filepath}")

    df        = load_events(filepath)
    dwell_df  = compute_dwell(df)
    flight_df = compute_flight(df)

    print(f"  Dwell rows : {len(dwell_df)}")
    print(f"  Flight rows: {len(flight_df)}")

    features  = extract_features(dwell_df, flight_df)
    print_summary(features)
    save_features(features, filepath)