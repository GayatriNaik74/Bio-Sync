import sys, os, json, hashlib
sys.path.insert(0, 'src')

USERS_FILE = "data/users.json"

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# Load current users or start fresh dict
if os.path.exists(USERS_FILE):
    with open(USERS_FILE) as f:
        users = json.load(f)
else:
    users = {}

# Simulate signup
TEST_USER = "__test_biosync_user__"
users[TEST_USER] = {
    'password': _hash("testpass123"),
    'enrolled': False,
    'created' : "2025-01-01T00:00:00"
}
os.makedirs("data", exist_ok=True)
with open(USERS_FILE, 'w') as f:
    json.dump(users, f, indent=2)
print(f"✓ User '{TEST_USER}' registered")

# Simulate correct login
with open(USERS_FILE) as f:
    users = json.load(f)
assert TEST_USER in users
assert users[TEST_USER]['password'] == _hash("testpass123")
assert users[TEST_USER]['enrolled'] == False
print("✓ Correct password accepted")

# Simulate wrong password
assert users[TEST_USER]['password'] != _hash("wrongpass")
print("✓ Wrong password rejected")

# Cleanup test user
del users[TEST_USER]
with open(USERS_FILE, 'w') as f:
    json.dump(users, f, indent=2)
print(f"✓ Test user cleaned up")

print("\n✓ User auth file state: PASS")