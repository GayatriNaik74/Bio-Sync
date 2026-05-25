"""
BioSync — src/mouse_features.py
Captures and extracts mouse behavioral features.
Runs alongside keystroke monitoring on the dashboard.

Features extracted:
  - Movement velocity (px/sec)
  - Movement acceleration
  - Path curvature
  - Click duration (dwell)
  - Click interval (flight)
  - Scroll speed
  - Idle time between movements
"""

import numpy as np
import time
from collections import deque


# ── Raw event buffer ─────────────────────────────────
_mouse_events   = deque(maxlen=2000)
_monitoring     = False


def start_collecting():
    global _monitoring
    _monitoring = True


def stop_collecting():
    global _monitoring
    _monitoring = False


def clear_buffer():
    _mouse_events.clear()


def get_events():
    return list(_mouse_events)


# ── pynput mouse listener ─────────────────────────────
def build_listener():
    """
    Returns a pynput mouse Listener.
    Call .start() to begin capturing.
    Call .stop() to end.
    """
    from pynput import mouse as mouse_module

    _press_times  = {}
    _last_move_ts = None
    _last_pos     = None

    def on_move(x, y):
        if not _monitoring:
            return
        now = int(time.time() * 1000)
        _mouse_events.append({
            'type'     : 'move',
            'x'        : x,
            'y'        : y,
            'timestamp': now,
        })

    def on_click(x, y, button, pressed):
        if not _monitoring:
            return
        now = int(time.time() * 1000)
        btn = str(button).split('.')[-1]
        if pressed:
            _press_times[btn] = now
            _mouse_events.append({
                'type'     : 'click_press',
                'x'        : x,
                'y'        : y,
                'button'   : btn,
                'timestamp': now,
            })
        else:
            press_t  = _press_times.pop(btn, now - 100)
            duration = now - press_t
            _mouse_events.append({
                'type'     : 'click_release',
                'x'        : x,
                'y'        : y,
                'button'   : btn,
                'timestamp': now,
                'duration' : duration,
            })

    def on_scroll(x, y, dx, dy):
        if not _monitoring:
            return
        now = int(time.time() * 1000)
        _mouse_events.append({
            'type'     : 'scroll',
            'x'        : x,
            'y'        : y,
            'dx'       : dx,
            'dy'       : dy,
            'timestamp': now,
        })

    listener = mouse_module.Listener(
        on_move    = on_move,
        on_click   = on_click,
        on_scroll  = on_scroll,
    )
    listener.daemon = True
    return listener


# ── Feature extraction ────────────────────────────────
def extract_mouse_features(events: list) -> dict:
    """
    Takes list of mouse events from get_events()
    and returns a feature dict for scoring.
    Returns None if insufficient data.
    """
    if not events or len(events) < 10:
        return None

    moves   = [e for e in events
               if e['type'] == 'move']
    clicks  = [e for e in events
               if e['type'] == 'click_release']
    scrolls = [e for e in events
               if e['type'] == 'scroll']

    features = {}

    # ── Movement velocity ─────────────────────────
    velocities = []
    for i in range(1, len(moves)):
        dx  = moves[i]['x'] - moves[i-1]['x']
        dy  = moves[i]['y'] - moves[i-1]['y']
        dt  = max(1,
              moves[i]['timestamp'] -
              moves[i-1]['timestamp'])
        dist = np.sqrt(dx**2 + dy**2)
        vel  = dist / dt * 1000  # px/sec
        if 0 < vel < 5000:       # filter noise
            velocities.append(vel)

    if velocities:
        features['mouse_vel_mean'] = float(
            np.mean(velocities))
        features['mouse_vel_std']  = float(
            np.std(velocities))
        features['mouse_vel_max']  = float(
            np.max(velocities))
        features['mouse_vel_cv']   = float(
            np.std(velocities) /
            (np.mean(velocities) + 1))
    else:
        features['mouse_vel_mean'] = 0.0
        features['mouse_vel_std']  = 0.0
        features['mouse_vel_max']  = 0.0
        features['mouse_vel_cv']   = 0.0

    # ── Acceleration ──────────────────────────────
    accels = []
    for i in range(1, len(velocities)):
        acc = abs(velocities[i] - velocities[i-1])
        accels.append(acc)

    features['mouse_accel_mean'] = float(
        np.mean(accels)) if accels else 0.0
    features['mouse_accel_std']  = float(
        np.std(accels))  if accels else 0.0

    # ── Path curvature ────────────────────────────
    # Measure how curved mouse paths are
    # Straight lines = low curvature
    curvatures = []
    window = 5
    for i in range(window, len(moves) - window):
        p0 = np.array([moves[i-window]['x'],
                       moves[i-window]['y']])
        p1 = np.array([moves[i]['x'],
                       moves[i]['y']])
        p2 = np.array([moves[i+window]['x'],
                       moves[i+window]['y']])
        # Angle between vectors
        v1 = p1 - p0
        v2 = p2 - p1
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 > 0 and n2 > 0:
            cos_a = np.dot(v1, v2) / (n1 * n2)
            cos_a = np.clip(cos_a, -1, 1)
            angle = np.arccos(cos_a)
            curvatures.append(float(angle))

    features['mouse_curve_mean'] = float(
        np.mean(curvatures)) if curvatures else 0.0
    features['mouse_curve_std']  = float(
        np.std(curvatures))  if curvatures else 0.0

    # ── Click duration (dwell) ────────────────────
    click_durations = [
        e['duration'] for e in clicks
        if 10 < e.get('duration', 0) < 2000
    ]
    features['click_dur_mean'] = float(
        np.mean(click_durations)
    ) if click_durations else 0.0
    features['click_dur_std']  = float(
        np.std(click_durations)
    ) if click_durations else 0.0

    # ── Click interval (flight) ───────────────────
    click_intervals = []
    for i in range(1, len(clicks)):
        interval = (clicks[i]['timestamp'] -
                    clicks[i-1]['timestamp'])
        if 0 < interval < 10000:
            click_intervals.append(float(interval))

    features['click_interval_mean'] = float(
        np.mean(click_intervals)
    ) if click_intervals else 0.0
    features['click_interval_std']  = float(
        np.std(click_intervals)
    ) if click_intervals else 0.0
    features['click_count'] = float(len(clicks))

    # ── Scroll behavior ───────────────────────────
    scroll_speeds = [
        abs(e['dy']) for e in scrolls
        if e.get('dy', 0) != 0
    ]
    features['scroll_speed_mean'] = float(
        np.mean(scroll_speeds)
    ) if scroll_speeds else 0.0
    features['scroll_count'] = float(len(scrolls))

    # ── Idle time ─────────────────────────────────
    idle_times = []
    for i in range(1, len(moves)):
        gap = (moves[i]['timestamp'] -
               moves[i-1]['timestamp'])
        if 500 < gap < 30000:  # 0.5s to 30s
            idle_times.append(float(gap))

    features['idle_mean'] = float(
        np.mean(idle_times)
    ) if idle_times else 0.0
    features['move_count'] = float(len(moves))

    return features


# ── Live display values (for dashboard cards) ─────────
def get_display_values(events: list) -> dict:
    """
    Returns simple human-readable values
    for the dashboard parameter cards.
    """
    if not events or len(events) < 5:
        return {
            'velocity' : '— px/s',
            'clicks'   : '0',
            'scrolls'  : '0',
            'idle'     : '— ms',
            'curve'    : '—',
        }

    moves   = [e for e in events
               if e['type'] == 'move']
    clicks  = [e for e in events
               if e['type'] == 'click_release']
    scrolls = [e for e in events
               if e['type'] == 'scroll']

    # Velocity
    velocities = []
    for i in range(1, min(len(moves), 50)):
        dx  = moves[i]['x'] - moves[i-1]['x']
        dy  = moves[i]['y'] - moves[i-1]['y']
        dt  = max(1,
              moves[i]['timestamp'] -
              moves[i-1]['timestamp'])
        vel = np.sqrt(dx**2 + dy**2) / dt * 1000
        if 0 < vel < 5000:
            velocities.append(vel)

    vel_str = (f"{np.mean(velocities):.0f} px/s"
               if velocities else "— px/s")

    # Idle
    idles = []
    for i in range(1, len(moves)):
        gap = (moves[i]['timestamp'] -
               moves[i-1]['timestamp'])
        if 500 < gap < 30000:
            idles.append(gap)

    idle_str = (f"{np.mean(idles):.0f} ms"
                if idles else "— ms")

    # Curvature label
    curvatures = []
    window = 5
    for i in range(window,
                   min(len(moves)-window, 100)):
        p0 = np.array([moves[i-window]['x'],
                       moves[i-window]['y']])
        p1 = np.array([moves[i]['x'],
                       moves[i]['y']])
        p2 = np.array([moves[i+window]['x'],
                       moves[i+window]['y']])
        v1, v2 = p1-p0, p2-p1
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 > 0 and n2 > 0:
            cos_a = np.clip(
                np.dot(v1, v2)/(n1*n2), -1, 1)
            curvatures.append(np.arccos(cos_a))

    if curvatures:
        avg_c = np.mean(curvatures)
        curve_str = ("High" if avg_c > 1.0
                     else "Medium" if avg_c > 0.5
                     else "Low")
    else:
        curve_str = "—"

    return {
        'velocity': vel_str,
        'clicks'  : str(len(clicks)),
        'scrolls' : str(len(scrolls)),
        'idle'    : idle_str,
        'curve'   : curve_str,
    }


# ── Mouse trust score ─────────────────────────────────
def compute_mouse_trust(live_features: dict,
                         baseline_features: dict,
                         baseline_std: dict) -> float:
    """
    Compare live mouse features against baseline.
    Returns trust score 0-100.
    Only called if baseline exists.
    """
    if not live_features or not baseline_features:
        return 85.0

    key_features = [
        'mouse_vel_mean',
        'mouse_vel_cv',
        'mouse_accel_mean',
        'click_dur_mean',
        'mouse_curve_mean',
    ]

    z_scores = []
    for feat in key_features:
        if (feat in live_features and
                feat in baseline_features):
            live = live_features[feat]
            mean = baseline_features[feat]
            std  = baseline_std.get(feat, 1.0) + 1e-9
            z    = abs((live - mean) / std)
            z_scores.append(z)

    if not z_scores:
        return 85.0

    mean_z = float(np.mean(z_scores))
    # mean_z=0 → 90, mean_z=1 → 72, mean_z=2 → 54
    # mean_z=3 → 36 (intruder)
    trust = float(np.clip(90 - mean_z * 18, 0, 100))
    return round(trust, 1)