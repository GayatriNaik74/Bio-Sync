"""
BioSync — src/admin_logger.py
Logs every scoring event to data/admin_logs.json.
Called from ui/dashboard.py every 30 seconds.
Admin dashboard reads this file to display all events.
"""

import os
import json
import datetime
import threading

ADMIN_LOGS_FILE  = "data/admin_logs.json"
ADMIN_CREDS_FILE = "data/admin.json"
MAX_EVENTS       = 1000   # max events stored per user
_lock            = threading.Lock()


# ── Initialise files if missing ───────────────────────
def init_admin_files():
    """Create admin files if they don't exist."""
    os.makedirs("data", exist_ok=True)

    # Admin credentials file
    if not os.path.exists(ADMIN_CREDS_FILE):
        import hashlib
        default = {
            "admin": {
                "password": hashlib.sha256(
                    "admin123".encode()
                ).hexdigest(),
                "role"    : "admin",
                "created" : datetime.datetime.now(
                ).isoformat()
            }
        }
        with open(ADMIN_CREDS_FILE, "w") as f:
            json.dump(default, f, indent=2)
        print("  ✓ Admin account created "
              "(username: admin, password: admin123)")

    # Admin logs file
    if not os.path.exists(ADMIN_LOGS_FILE):
        with open(ADMIN_LOGS_FILE, "w") as f:
            json.dump({}, f, indent=2)


# ── Verify admin credentials ──────────────────────────
def verify_admin(username: str,
                 password: str) -> bool:
    """Returns True if admin credentials are valid."""
    import hashlib
    if not os.path.exists(ADMIN_CREDS_FILE):
        init_admin_files()
    try:
        with open(ADMIN_CREDS_FILE) as f:
            admins = json.load(f)
        pw_hash = hashlib.sha256(
            password.encode()).hexdigest()
        if (username in admins and
                admins[username]["password"]
                == pw_hash):
            return True
    except Exception:
        pass
    return False


# ── Log a scoring event ───────────────────────────────
def log_event(username  : str,
              score     : float,
              risk      : str,
              dwell_ms  : float = 0.0,
              flight_ms : float = 0.0,
              mouse_vel : float = 0.0,
              locked    : bool  = False,
              session_id: str   = "",
              tx_hash   : str   = ""):
    """
    Write one scoring event to admin_logs.json.
    Thread-safe.
    """
    if not username:
        return

    event = {
        "timestamp" : datetime.datetime.now(
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "score"     : round(float(score), 1),
        "risk"      : risk,
        "dwell_ms"  : round(float(dwell_ms), 1),
        "flight_ms" : round(float(flight_ms), 1),
        "mouse_vel" : round(float(mouse_vel), 1),
        "locked"    : locked,
        "session_id": str(session_id)[:16],
        "tx_hash"   : str(tx_hash)[:20],
    }

    with _lock:
        try:
            # Load existing logs
            if os.path.exists(ADMIN_LOGS_FILE):
                with open(ADMIN_LOGS_FILE) as f:
                    logs = json.load(f)
            else:
                logs = {}

            # Add event for this user
            if username not in logs:
                logs[username] = {
                    "events"      : [],
                    "enrolled_on" : "",
                    "last_seen"   : "",
                    "total_locks" : 0,
                }

            logs[username]["events"].insert(0, event)
            logs[username]["last_seen"] = (
                event["timestamp"])

            # Track locks
            if locked:
                logs[username]["total_locks"] = (
                    logs[username].get(
                        "total_locks", 0) + 1)

            # Trim to max events
            logs[username]["events"] = (
                logs[username]["events"][:MAX_EVENTS])

            # Save
            with open(ADMIN_LOGS_FILE, "w") as f:
                json.dump(logs, f, indent=2)

        except Exception as e:
            print(f"  Admin log error: {e}")


# ── Set user enrolled date ────────────────────────────
def set_enrolled_date(username: str):
    """Called when user completes enrollment."""
    with _lock:
        try:
            if os.path.exists(ADMIN_LOGS_FILE):
                with open(ADMIN_LOGS_FILE) as f:
                    logs = json.load(f)
            else:
                logs = {}

            if username not in logs:
                logs[username] = {
                    "events"      : [],
                    "total_locks" : 0,
                }
            logs[username]["enrolled_on"] = (
                datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"))
            logs[username]["last_seen"] = (
                datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"))

            with open(ADMIN_LOGS_FILE, "w") as f:
                json.dump(logs, f, indent=2)
        except Exception:
            pass


# ── Read all logs (for admin dashboard) ───────────────
def get_all_logs() -> dict:
    """Returns all logs for all users."""
    try:
        if os.path.exists(ADMIN_LOGS_FILE):
            with open(ADMIN_LOGS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


# ── Get user summary ──────────────────────────────────
def get_user_summary(username: str) -> dict:
    """
    Returns summary stats for one user:
    total events, total locks, last score,
    last risk, intrusions today.
    """
    logs = get_all_logs()
    if username not in logs:
        return {}

    user_data = logs[username]
    events    = user_data.get("events", [])
    today     = datetime.date.today().strftime(
        "%Y-%m-%d")

    intrusions_today = sum(
        1 for e in events
        if e.get("risk") in ("MEDIUM", "HIGH")
        and e.get("timestamp", "").startswith(today)
    )
    locks_today = sum(
        1 for e in events
        if e.get("locked")
        and e.get("timestamp", "").startswith(today)
    )

    last_event = events[0] if events else {}

    return {
        "username"        : username,
        "enrolled_on"     : user_data.get(
            "enrolled_on", "—"),
        "last_seen"       : user_data.get(
            "last_seen", "—"),
        "total_events"    : len(events),
        "total_locks"     : user_data.get(
            "total_locks", 0),
        "intrusions_today": intrusions_today,
        "locks_today"     : locks_today,
        "last_score"      : last_event.get(
            "score", "—"),
        "last_risk"       : last_event.get(
            "risk", "—"),
        "last_timestamp"  : last_event.get(
            "timestamp", "—"),
    }


# ── Export user events as CSV ─────────────────────────
def export_user_csv(username: str,
                    filepath: str) -> bool:
    """Export all events for a user to CSV."""
    import csv
    logs = get_all_logs()
    if username not in logs:
        return False
    events = logs[username].get("events", [])
    if not events:
        return False
    try:
        fields = ["timestamp", "score", "risk",
                  "dwell_ms", "flight_ms",
                  "mouse_vel", "locked",
                  "session_id", "tx_hash"]
        with open(filepath, "w",
                  newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fields)
            writer.writeheader()
            for evt in events:
                writer.writerow(
                    {k: evt.get(k, "")
                     for k in fields})
        return True
    except Exception:
        return False


# ── Export all users summary CSV ──────────────────────
def export_summary_csv(filepath: str) -> bool:
    """Export summary of all users to CSV."""
    import csv
    logs = get_all_logs()
    if not logs:
        return False
    try:
        fields = ["username", "enrolled_on",
                  "last_seen", "total_events",
                  "total_locks",
                  "intrusions_today",
                  "last_score", "last_risk"]
        with open(filepath, "w",
                  newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fields)
            writer.writeheader()
            for uname in logs:
                summary = get_user_summary(uname)
                writer.writerow(
                    {k: summary.get(k, "")
                     for k in fields})
        return True
    except Exception:
        return False


# ── Initialise on import ──────────────────────────────
init_admin_files()