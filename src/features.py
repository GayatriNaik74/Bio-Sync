"""
BioSync Phase 1 — Feature Extraction
Reads raw keystroke CSV and computes:
  - Dwell time features
  - Flight time features
  - Digraph timing (key pair timings)
  - Trigraph timing (key triple timings)
Usage: python src/features.py data/raw/session_XXXX.csv
"""

import sys
import os
import json
import numpy as np
import pandas as pd

# ── Load raw events ──────────────────────────────────
def load_events(filepath):
    df = pd.read_csv(filepath)
    print(f"  Loaded {len(df)} events from {filepath}")
    return df

# ── Compute dwell times ──────────────────────────────
def compute_dwell(df):
    """
    Read pre-calculated dwell_ms from CSV.
    Falls back to press/release computation.
    """
    if 'dwell_ms' in df.columns:
        dwell_df = df[['key', 'dwell_ms']].copy()
        dwell_df = dwell_df[
            (dwell_df['dwell_ms'] > 10) &
            (dwell_df['dwell_ms'] < 2000)
        ].reset_index(drop=True)
        return dwell_df

    # Fallback: compute from press/release pairs
    dwells    = []
    press_map = {}
    for _, row in df.iterrows():
        key = row['key']
        ts  = row['timestamp_ms']
        if row['event_type'] == 'press':
            press_map[key] = ts
        elif (row['event_type'] == 'release'
              and key in press_map):
            dwell = ts - press_map[key]
            if 10 < dwell < 2000:
                dwells.append({
                    'key'     : key,
                    'dwell_ms': dwell})
            del press_map[key]
    return pd.DataFrame(dwells)

# ── Compute flight times ─────────────────────────────
def compute_flight(df):
    """
    Read pre-calculated flight_ms from CSV.
    Falls back to press-to-press computation.
    """
    if 'flight_ms' in df.columns:
        flight_df = df[['key', 'flight_ms']].copy()
        flight_df = flight_df[
            (flight_df['flight_ms'] > 1) &
            (flight_df['flight_ms'] < 2000)
        ].reset_index(drop=True)
        flight_df = flight_df.rename(
            columns={'key': 'to_key'})
        flight_df['from_key'] = \
            flight_df['to_key'].shift(1).fillna('')
        return flight_df

    # Fallback
    flights          = []
    last_release_time = None
    last_release_key  = None
    for _, row in df.iterrows():
        ts  = row['timestamp_ms']
        key = row['key']
        if row['event_type'] == 'release':
            last_release_time = ts
            last_release_key  = key
        elif (row['event_type'] == 'press'
              and last_release_time):
            flight = ts - last_release_time
            if 0 < flight < 2000:
                flights.append({
                    'from_key' : last_release_key,
                    'to_key'   : key,
                    'flight_ms': flight
                })
    return pd.DataFrame(flights)

# ── Compute digraph timings ──────────────────────────
def compute_digraphs(df):
    """
    Digraph = time between consecutive key presses.
    Returns dict of {bigram: [timings]} for common pairs.
    Only computed for press events.
    """
    # Most common English digraphs
    DIGRAPHS = [
        'th','he','in','er','an','re','on','en',
        'at','es','st','nt','io','to','is','or',
        'ti','as','te','ng','ou','ha','nd','it',
        'ed','no','se','al','of','hi'
    ]

    press_events = df[
        df['event_type'] == 'press'
    ].reset_index(drop=True)

    digraph_times = {d: [] for d in DIGRAPHS}

    for i in range(len(press_events) - 1):
        k1 = str(press_events.iloc[i]['key']).lower()
        k2 = str(press_events.iloc[i+1]['key']).lower()
        bigram = k1 + k2

        if bigram in digraph_times:
            t1 = press_events.iloc[i]['timestamp_ms']
            t2 = press_events.iloc[i+1]['timestamp_ms']
            interval = t2 - t1
            if 0 < interval < 1000:
                digraph_times[bigram].append(
                    float(interval))

    return digraph_times

# ── Compute trigraph timings ─────────────────────────
def compute_trigraphs(df):
    """
    Trigraph = time across 3 consecutive key presses.
    Returns dict of {trigram: [timings]} for common triples.
    """
    # Most common English trigraphs
    TRIGRAPHS = [
        'the','ing','and','ion','ent','ati','for',
        'her','ter','hat','thi','nth','int','ere',
        'tio','ver','all','wit','his','tha','our',
        'ons','ess','ive','tin','men','est','are'
    ]

    press_events = df[
        df['event_type'] == 'press'
    ].reset_index(drop=True)

    trigraph_times = {t: [] for t in TRIGRAPHS}

    for i in range(len(press_events) - 2):
        k1 = str(press_events.iloc[i]['key']).lower()
        k2 = str(press_events.iloc[i+1]['key']).lower()
        k3 = str(press_events.iloc[i+2]['key']).lower()
        trigram = k1 + k2 + k3

        if trigram in trigraph_times:
            t1 = press_events.iloc[i]['timestamp_ms']
            t3 = press_events.iloc[i+2]['timestamp_ms']
            interval = t3 - t1
            if 0 < interval < 2000:
                trigraph_times[trigram].append(
                    float(interval))

    return trigraph_times

# ── Extract digraph features ─────────────────────────
def extract_digraph_features(digraph_times: dict,
                              trigraph_times: dict) -> dict:
    """
    Summarise digraph and trigraph timings into
    statistical features for the model.
    """
    features = {}

    # ── Digraph stats ────────────────────────────────
    all_dg_times = []
    dg_found     = 0

    for bigram, times in digraph_times.items():
        if times:
            dg_found += 1
            all_dg_times.extend(times)
            features[f'dg_{bigram}_mean'] = float(
                np.mean(times))
            features[f'dg_{bigram}_std']  = float(
                np.std(times)) if len(times) > 1 else 0.0
        else:
            features[f'dg_{bigram}_mean'] = 0.0
            features[f'dg_{bigram}_std']  = 0.0

    # Overall digraph stats
    if all_dg_times:
        features['dg_overall_mean'] = float(
            np.mean(all_dg_times))
        features['dg_overall_std']  = float(
            np.std(all_dg_times))
        features['dg_overall_min']  = float(
            np.min(all_dg_times))
        features['dg_overall_max']  = float(
            np.max(all_dg_times))
        features['dg_found_count']  = float(dg_found)
    else:
        features['dg_overall_mean'] = 0.0
        features['dg_overall_std']  = 0.0
        features['dg_overall_min']  = 0.0
        features['dg_overall_max']  = 0.0
        features['dg_found_count']  = 0.0

    # ── Trigraph stats ───────────────────────────────
    all_tg_times = []
    tg_found     = 0

    for trigram, times in trigraph_times.items():
        if times:
            tg_found += 1
            all_tg_times.extend(times)
            features[f'tg_{trigram}_mean'] = float(
                np.mean(times))
        else:
            features[f'tg_{trigram}_mean'] = 0.0

    # Overall trigraph stats
    if all_tg_times:
        features['tg_overall_mean'] = float(
            np.mean(all_tg_times))
        features['tg_overall_std']  = float(
            np.std(all_tg_times))
        features['tg_found_count']  = float(tg_found)
    else:
        features['tg_overall_mean'] = 0.0
        features['tg_overall_std']  = 0.0
        features['tg_found_count']  = 0.0

    return features

# ── Summarise into one feature vector ────────────────
def extract_features(dwell_df, flight_df,
                     df_raw=None) -> dict:
    """
    Compute full feature vector including
    dwell, flight, digraph, and trigraph features.
    """
    d = dwell_df['dwell_ms'].values
    f = flight_df['flight_ms'].values if \
        'flight_ms' in flight_df.columns else \
        np.array([100.0])

    if len(d) == 0: d = np.array([100.0])
    if len(f) == 0: f = np.array([100.0])

    features = {
        # ── Dwell time statistics ─────────────────
        'dwell_mean'        : float(np.mean(d)),
        'dwell_std'         : float(np.std(d)),
        'dwell_min'         : float(np.min(d)),
        'dwell_max'         : float(np.max(d)),
        'dwell_median'      : float(np.median(d)),
        'dwell_p25'         : float(np.percentile(d, 25)),
        'dwell_p75'         : float(np.percentile(d, 75)),

        # ── Flight time statistics ────────────────
        'flight_mean'       : float(np.mean(f)),
        'flight_std'        : float(np.std(f)),
        'flight_min'        : float(np.min(f)),
        'flight_max'        : float(np.max(f)),
        'flight_median'     : float(np.median(f)),
        'flight_p25'        : float(np.percentile(f, 25)),
        'flight_p75'        : float(np.percentile(f, 75)),

        # ── Derived features ──────────────────────
        'dwell_flight_ratio': float(
            np.mean(d) / (np.mean(f) + 1)),
        'total_keypresses'  : int(len(d)),

        # ── Speed features ────────────────────────
        'speed_cv'          : float(
            np.std(f) / (np.mean(f) + 1)),
        'dwell_cv'          : float(
            np.std(d) / (np.mean(d) + 1)),
        'burst_ratio'       : float(
            np.sum(f < 80) / (len(f) + 1)),
    }

    # ── Add digraph + trigraph if raw df provided ──
    if df_raw is not None:
        try:
            dg_times = compute_digraphs(df_raw)
            tg_times = compute_trigraphs(df_raw)
            ng_feats = extract_digraph_features(
                dg_times, tg_times)
            features.update(ng_feats)
        except Exception:
            pass

    return features

# ── Print summary ─────────────────────────────────────
def print_summary(features):
    print()
    print("=" * 48)
    print("  Feature Summary")
    print("=" * 48)
    print(f"  Avg dwell time   : "
          f"{features['dwell_mean']:.1f} ms")
    print(f"  Avg flight time  : "
          f"{features['flight_mean']:.1f} ms")
    print(f"  Dwell std dev    : "
          f"{features['dwell_std']:.1f} ms")
    print(f"  Total keypresses : "
          f"{features['total_keypresses']}")
    if 'dg_overall_mean' in features:
        print(f"  Avg digraph time : "
              f"{features['dg_overall_mean']:.1f} ms")
        print(f"  Digraphs found   : "
              f"{int(features['dg_found_count'])}")
    if 'tg_overall_mean' in features:
        print(f"  Avg trigraph time: "
              f"{features['tg_overall_mean']:.1f} ms")
        print(f"  Trigraphs found  : "
              f"{int(features['tg_found_count'])}")
    print()

# ── Save processed features ───────────────────────────
def save_features(features, source_file):
    out_dir  = "data/processed"
    basename = os.path.splitext(
        os.path.basename(source_file))[0]
    out_path = os.path.join(
        out_dir, f"{basename}_features.json")
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(
            {k: float(v)
             for k, v in features.items()},
            f, indent=2)
    print(f"  ✓ Features saved → {out_path}")
    return out_path

# ── Main ──────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/features.py "
              "data/raw/session_XXX.csv")
        sys.exit(1)

    filepath  = sys.argv[1]
    print(f"\n  Processing: {filepath}")

    df        = load_events(filepath)
    dwell_df  = compute_dwell(df)
    flight_df = compute_flight(df)

    print(f"  Dwell rows  : {len(dwell_df)}")
    print(f"  Flight rows : {len(flight_df)}")

    features  = extract_features(
        dwell_df, flight_df, df_raw=df)
    print_summary(features)
    save_features(features, filepath)

    # Show digraph details
    dg = compute_digraphs(df)
    print("  Top digraphs found:")
    found = {k:v for k,v in dg.items() if v}
    for bigram, times in sorted(
            found.items(),
            key=lambda x: -len(x[1]))[:10]:
        print(f"    '{bigram}' → "
              f"mean={np.mean(times):.0f}ms "
              f"n={len(times)}")