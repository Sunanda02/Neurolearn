"""
scripts/seed_demo_accounts.py — creates a few demo accounts through the
REAL signup flow (bcrypt-hashed passwords, real JWTs), then awards each
one a realistic amount of XP through the REAL /api/student/xp path — not
by writing fake rows directly into the database. This is deliberately
different from the old TinyDB seed, which inserted six fictional
students (Priya Sharma, Marcus Chen, ...) directly into a leaderboard
table that nothing else ever touched.

Every account created here is a fully functional login you can actually
use to sign in and see the app from a "real" student's perspective.

Run from backend/, with the server already running:
    python3 scripts/seed_demo_accounts.py
"""
import requests

BASE = "http://localhost:8000/api"

DEMO_ACCOUNTS = [
    {"name": "Priya Sharma",  "email": "priya@example.com",  "password": "demo12345", "xp": 12500},
    {"name": "Marcus Chen",   "email": "marcus@example.com", "password": "demo12345", "xp": 11200},
    {"name": "Sofia Reyes",   "email": "sofia@example.com",  "password": "demo12345", "xp": 10800},
    {"name": "Aiden Okafor",  "email": "aiden@example.com",  "password": "demo12345", "xp": 9500},
    {"name": "Emma Williams", "email": "emma@example.com",   "password": "demo12345", "xp": 8900},
    {"name": "Alex Johnson",  "email": "alex@example.com",   "password": "demo12345", "xp": 4250},
]


def main():
    for acct in DEMO_ACCOUNTS:
        r = requests.post(f"{BASE}/auth/signup", json={
            "email": acct["email"], "password": acct["password"], "name": acct["name"],
        })
        if r.status_code == 409:
            # Already exists — log in instead so we can still top up XP.
            r = requests.post(f"{BASE}/auth/login", json={
                "email": acct["email"], "password": acct["password"],
            })
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Award XP through the real endpoint (level-up math included) —
        # not a direct DB write.
        requests.post(f"{BASE}/student/xp", headers=headers, json={
            "student_id": "ignored-server-derives-from-token",
            "amount": acct["xp"],
            "reason": "demo seed",
        }).raise_for_status()

        print(f"Seeded {acct['name']} <{acct['email']}> with {acct['xp']} XP "
              f"(password: {acct['password']})")


if __name__ == "__main__":
    main()
