"""
Local OTP end-to-end smoke test.
Run AFTER starting the Flask server locally:
    $env:SMTP_PASS="your-app-password"
    python run.py          # in one terminal (port 5002)
    python _test_otp.py    # in another terminal

Tests:
  1. /api/auth/send-otp  -> expect 200 + email delivered
  2. /api/auth/send-otp  -> expect 429 (30s cooldown)
  3. /api/auth/verify-otp with wrong OTP -> expect 401
  4. Manually input the real OTP from email -> expect 200 + JWT token
  5. Rate-limit: send 5 OTPs rapidly -> 6th should return 429 (15-min window)
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5002"

# ── CONFIGURE THESE ───────────────────────────────────────────────────────────
TEST_EMAIL   = "gangarealty.lms@gmail.com"   # must exist in users table
TENANT_SLUG  = "ganga"                        # the tenant slug for this user
# ─────────────────────────────────────────────────────────────────────────────


def _post(path, payload, label):
    url = BASE + path
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=body,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
            print(f"  [{r.status}] {label}: {json.dumps(data)[:200]}")
            return r.status, data
    except urllib.error.HTTPError as e:
        data = json.loads(e.read())
        print(f"  [{e.code}] {label}: {json.dumps(data)[:200]}")
        return e.code, data


print("=" * 60)
print("OTP LOCAL SMOKE TEST")
print("=" * 60)

# 1. Send OTP
print("\n[1] Send OTP (expect 200)...")
status, body = _post("/api/auth/send-otp",
                     {"email": TEST_EMAIL, "tenant_slug": TENANT_SLUG},
                     "send-otp")
assert status == 200, f"Expected 200, got {status}"
print("    -> OTP email sent. Check inbox:", TEST_EMAIL)

# 2. Immediate resend (expect 429 cooldown)
print("\n[2] Immediate resend (expect 429 cooldown)...")
status, body = _post("/api/auth/send-otp",
                     {"email": TEST_EMAIL, "tenant_slug": TENANT_SLUG},
                     "send-otp resend")
assert status == 429, f"Expected 429, got {status}"
print(f"    -> Cooldown working. Wait: {body.get('cooldown')}s")

# 3. Wrong OTP (expect 401)
print("\n[3] Wrong OTP (expect 401)...")
status, body = _post("/api/auth/verify-otp",
                     {"email": TEST_EMAIL, "otp": "000000", "tenant_slug": TENANT_SLUG},
                     "verify-otp wrong")
assert status == 401, f"Expected 401, got {status}"
print("    -> Wrong OTP rejected correctly")

# 4. Correct OTP from email (manual step)
print("\n[4] Enter the 6-digit OTP from your email inbox:")
real_otp = input("    OTP: ").strip()
if not real_otp:
    print("    Skipped.")
else:
    status, body = _post("/api/auth/verify-otp",
                         {"email": TEST_EMAIL, "otp": real_otp, "tenant_slug": TENANT_SLUG},
                         "verify-otp real")
    if status == 200:
        print(f"    -> LOGIN SUCCESS. User: {body.get('user', {}).get('name')}")
        print(f"    -> Role: {body.get('user', {}).get('role')}")
        print(f"    -> Products: {[p.get('name') for p in body.get('products', [])]}")
        token = body.get("token", "")
        print(f"    -> JWT (first 40 chars): {token[:40]}...")
    else:
        print(f"    -> FAILED: {body}")

# 5. Rate limit test (optional, destructive — uses 4 more OTP slots)
print("\n[5] Rate-limit test? (Sends up to 4 more OTPs to hit the 5/15min cap)")
ans = input("    Run rate-limit test? [y/N]: ").strip().lower()
if ans == "y":
    # Wait for 30s cooldown to expire first
    print("    Waiting 31s for cooldown to expire...")
    time.sleep(31)
    hit_limit = False
    for i in range(4):
        print(f"    Sending OTP #{i+2} of 5...")
        status, body = _post("/api/auth/send-otp",
                             {"email": TEST_EMAIL, "tenant_slug": TENANT_SLUG},
                             f"rate-limit send #{i+2}")
        if status == 429 and "Too many OTP requests" in body.get("error", ""):
            print(f"    -> Rate limit hit at attempt #{i+2}. PASS.")
            hit_limit = True
            break
        time.sleep(31)  # wait for cooldown between each
    if not hit_limit:
        print("    -> Rate limit NOT triggered. Check _OTP_RATE_LIMIT setting.")
else:
    print("    Skipped.")

print("\n" + "=" * 60)
print("Smoke test complete.")
print("=" * 60)
