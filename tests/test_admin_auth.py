import sys
sys.path.insert(0, 'src')
from admin_logger import verify_admin

# Test 1: correct default credentials
result = verify_admin("admin", "admin123")
assert result == True, "Should accept correct credentials"
print("✓ Correct credentials accepted")

# Test 2: wrong password
result = verify_admin("admin", "wrongpassword")
assert result == False, "Should reject wrong password"
print("✓ Wrong password rejected")

# Test 3: non-existent user
result = verify_admin("hacker", "admin123")
assert result == False, "Should reject unknown user"
print("✓ Unknown user rejected")

print("✓ Admin auth: PASS")