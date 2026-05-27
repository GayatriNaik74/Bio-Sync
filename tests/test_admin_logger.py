import sys
sys.path.insert(0, 'src')
from admin_logger import log_event, get_user_summary, get_all_logs

# Write a test event
log_event(
    username   = "test_user",
    score      = 82.5,
    risk       = "LOW",
    dwell_ms   = 110.0,
    flight_ms  = 145.0,
    mouse_vel  = 320.0,
    locked     = False,
    session_id = "sess_test_001",
    tx_hash    = ""
)
print("✓ Event written")

# Read it back
summary = get_user_summary("test_user")
print(f"  Last score : {summary['last_score']}")
print(f"  Last risk  : {summary['last_risk']}")
print(f"  Total events: {summary['total_events']}")

# Assert
assert summary['last_score'] == 82.5, "Score mismatch"
assert summary['last_risk']  == "LOW", "Risk mismatch"
print("✓ Admin logger: PASS")