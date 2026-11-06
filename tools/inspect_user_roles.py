# -*- coding: utf-8 -*-
import sys, os, sqlite3
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.database as db
from core.tenants import get_all_merchants, DEFAULT_TENANT

path = db.get_db_path()
conn = sqlite3.connect(path)
cur = conn.cursor()

total = cur.execute("SELECT COUNT(1) FROM users").fetchone()[0]
print("Total rows in users table:", total)

roles = cur.execute("SELECT role, COUNT(1) FROM users GROUP BY role").fetchall()
print("Role distribution:", roles)

admin_emails = [DEFAULT_TENANT["admin_email"].strip().lower()]
for m in get_all_merchants():
    ae = (m.get("admin_email") or "").strip().lower()
    if ae and ae not in admin_emails:
        admin_emails.append(ae)
print("Admin / merchant admin emails to exclude:", admin_emails)

cur.execute("SELECT uid, email, role FROM users WHERE role IN ('admin', 'merchant_admin') OR LOWER(email) IN ({})".format(','.join('?' for _ in admin_emails)), admin_emails)
excluded = cur.fetchall()
print("Excluded accounts count:", len(excluded))
for ex in excluded:
    print("  Excluded:", ex)

users_with_castles = db.get_all_users_with_castles()
print("get_all_users_with_castles() returned count:", len(users_with_castles))
conn.close()
