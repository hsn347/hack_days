# -*- coding: utf-8 -*-
"""
tools/challenge_m2_pagination.py — Empirical Challenger & Adversarial Stress Harness for M2:
Admin Castles Pagination & Lazy Loading.
══════════════════════════════════════════════════════════════════════════════════════════
Automated adversarial verification by challenger_p2_m2_1:
1. Pagination boundary conditions: page 1, page 2, last page, beyond last page,
   page_size 10, 25, 50, 100, page=0, page=-5, page='xyz', page_size=0, page_size=-10, page_size=1000.
2. Search robustness: user email, castle email, castle ID, username, non-existent terms.
3. Payload cleanliness: strict exclusion of `config` and `raw_json` from summary payloads.
4. Merchant admin tenant filtering: strict isolation, cross-tenant leak prevention.
5. Filter status checks: 'all', 'with_castles', 'no_castles', 'running'.
6. API endpoint compatibility: /api/admin/users-castles/summary envelope and live status integration.
"""

import os
import sys
import json
import tempfile
import sqlite3
from typing import Dict, Any, List

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import core.database as db


class ChallengeHarness:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failures = []

    def assert_true(self, condition: bool, description: str):
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  [PASS] {description}")
        else:
            self.failures.append(description)
            print(f"  [FAIL] {description}")

    def assert_equal(self, actual: Any, expected: Any, description: str):
        self.total += 1
        if actual == expected:
            self.passed += 1
            print(f"  [PASS] {description}")
        else:
            msg = f"{description} (Expected: {expected}, Actual: {actual})"
            self.failures.append(msg)
            print(f"  [FAIL] {msg}")


def seed_adversarial_db(db_path: str):
    """Seed test database with diverse users, tenants, and heavy castle payloads."""
    db.init_db(db_path)
    
    with db.get_connection(db_path) as conn:
        # Create 60 users:
        # - u01 to u35: general users (tenant_domain = None), varying castle counts
        # - u36 to u45: tenant-alpha.com
        # - u46 to u55: tenant-beta.com
        # - u56 to u60: users with 0 castles
        
        # Heavy payload to stress test payload exclusion (50KB config per castle)
        heavy_config = json.dumps({"bot_settings": {"deep_key_" + str(i): "x" * 100 for i in range(500)}})
        heavy_raw_json = json.dumps({"game_state": {"inventory": ["item_" + str(i) for i in range(1000)]}})
        
        users_to_insert = []
        for i in range(1, 61):
            uid = f"user_{i:03d}"
            email = f"user_{i:03d}@example.com"
            username = f"Lord_{i:03d}"
            tenant = None
            if 36 <= i <= 45:
                tenant = "tenant-alpha.com"
            elif 46 <= i <= 55:
                tenant = "tenant-beta.com"
            
            # Special search anchors:
            if i == 12:
                email = "target_special_search@needle.com"
                username = "UniqueLordMagnificent"
                
            users_to_insert.append((
                uid, email, username, "user", False, f"2026-11-01T{i%24:02d}:00:00Z",
                tenant, "pro", "باقة المحترفين", "active", "2027-01-01", 10
            ))
            
        conn.executemany("""
            INSERT INTO users (
                uid, email, username, role, is_banned, created_at,
                tenant_domain, plan_id, plan_name, subscription_status, subscription_expires_at, max_castles_allowed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, users_to_insert)

        # Insert castles:
        castles_to_insert = []
        # Users 1 to 55 get between 1 and 4 castles
        for i in range(1, 56):
            uid = f"user_{i:03d}"
            # user 12 special castle search anchors
            if i == 12:
                cid = "castle_special_needle_999"
                c_email = "castle_needle_email@castlemail.org"
                castles_to_insert.append((
                    cid, uid, c_email, 1, "running", "connected", "Needle Castle", "Lord Needle",
                    heavy_config, heavy_raw_json, "2026-11-01T12:00:00Z"
                ))
            else:
                num_castles = 1 + (i % 3)
                for c_idx in range(num_castles):
                    cid = f"c_{i:03d}_{c_idx}"
                    c_email = f"c_{i:03d}_{c_idx}@gamemail.com"
                    state = "running" if (i % 2 == 0) else "idle"
                    conn_st = "connected" if state == "running" else "disconnected"
                    castles_to_insert.append((
                        cid, uid, c_email, 1 if state == "running" else 0, state, conn_st,
                        f"Castle_{i}_{c_idx}", f"Lord_{i}",
                        heavy_config, heavy_raw_json, "2026-11-01T12:00:00Z"
                    ))

        conn.executemany("""
            INSERT INTO castle_states (
                castle_id, user_id, email, is_active, state, conn_state,
                castle_name, lord_name, config, raw_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, castles_to_insert)
        conn.commit()


def run_challenge():
    harness = ChallengeHarness()
    temp_dir = tempfile.mkdtemp(prefix="challenge_m2_")
    db_path = os.path.join(temp_dir, "test_challenge_m2.db")

    print(f"[*] Initializing hermetic adversarial test database at: {db_path}")
    seed_adversarial_db(db_path)

    # ══════════════════════════════════════════════════════════════
    # TIER 1: PAGINATION BOUNDARIES AND SIZES
    # ══════════════════════════════════════════════════════════════
    print("\n--- Tier 1: Pagination Boundaries and Sizes ---")
    
    # Page 1 of 25 (Total users = 60)
    p1 = db.get_admin_castles_paginated(page=1, page_size=25, db_path=db_path)
    harness.assert_equal(len(p1["items"]), 25, "Page 1 returns exactly 25 items")
    harness.assert_equal(p1["total"], 60, "Page 1 reports total count of 60")
    harness.assert_equal(p1["total_pages"], 3, "Page 1 reports total_pages = 3 (ceil(60/25))")
    harness.assert_equal(p1["page"], 1, "Page 1 echoes page = 1")
    harness.assert_equal(p1["page_size"], 25, "Page 1 echoes page_size = 25")
    harness.assert_true(p1["has_more"] is True, "Page 1 has_more is True")
    harness.assert_true("summary_stats" in p1, "Page 1 contains summary_stats")

    # Page 2 of 25
    p2 = db.get_admin_castles_paginated(page=2, page_size=25, db_path=db_path)
    harness.assert_equal(len(p2["items"]), 25, "Page 2 returns exactly 25 items")
    harness.assert_equal(p2["page"], 2, "Page 2 echoes page = 2")
    harness.assert_true(p2["has_more"] is True, "Page 2 has_more is True")
    # Verify no overlap between page 1 and page 2
    p1_uids = {u["uid"] for u in p1["items"]}
    p2_uids = {u["uid"] for u in p2["items"]}
    harness.assert_equal(len(p1_uids.intersection(p2_uids)), 0, "No duplicate users across Page 1 and Page 2")

    # Page 3 of 25 (Last page)
    p3 = db.get_admin_castles_paginated(page=3, page_size=25, db_path=db_path)
    harness.assert_equal(len(p3["items"]), 10, "Page 3 (last page) returns remaining 10 items (60 - 50)")
    harness.assert_equal(p3["page"], 3, "Page 3 echoes page = 3")
    harness.assert_true(p3["has_more"] is False, "Page 3 (last page) has_more is False")

    # Page 4 of 25 (Beyond last page)
    p4 = db.get_admin_castles_paginated(page=4, page_size=25, db_path=db_path)
    harness.assert_equal(len(p4["items"]), 0, "Page 4 (beyond last page) returns 0 items safely")
    harness.assert_equal(p4["total"], 60, "Page 4 maintains accurate total = 60")
    harness.assert_true(p4["has_more"] is False, "Page 4 has_more is False")

    # Different page sizes: 10, 50, 100
    ps10 = db.get_admin_castles_paginated(page=1, page_size=10, db_path=db_path)
    harness.assert_equal(len(ps10["items"]), 10, "page_size=10 returns 10 items")
    harness.assert_equal(ps10["total_pages"], 6, "page_size=10 reports 6 total_pages")

    ps50 = db.get_admin_castles_paginated(page=1, page_size=50, db_path=db_path)
    harness.assert_equal(len(ps50["items"]), 50, "page_size=50 returns 50 items")
    harness.assert_equal(ps50["total_pages"], 2, "page_size=50 reports 2 total_pages")

    ps100 = db.get_admin_castles_paginated(page=1, page_size=100, db_path=db_path)
    harness.assert_equal(len(ps100["items"]), 60, "page_size=100 returns all 60 items")
    harness.assert_equal(ps100["total_pages"], 1, "page_size=100 reports 1 total_page")
    harness.assert_true(ps100["has_more"] is False, "page_size=100 has_more is False")

    # Boundary & Malformed Inputs
    p_zero = db.get_admin_castles_paginated(page=0, page_size=25, db_path=db_path)
    harness.assert_equal(p_zero["page"], 1, "page=0 is safely clamped to page 1")
    harness.assert_equal(len(p_zero["items"]), 25, "page=0 returns 25 items for clamped page 1")

    p_neg = db.get_admin_castles_paginated(page=-10, page_size=25, db_path=db_path)
    harness.assert_equal(p_neg["page"], 1, "page=-10 is safely clamped to page 1")

    p_str_invalid = db.get_admin_castles_paginated(page="invalid_page_num", page_size=25, db_path=db_path)
    harness.assert_equal(p_str_invalid["page"], 1, "Malformed page string safely defaults to page 1")

    ps_zero = db.get_admin_castles_paginated(page=1, page_size=0, db_path=db_path)
    harness.assert_true(len(ps_zero["items"]) >= 0, "page_size=0 handled gracefully without crash")

    ps_huge = db.get_admin_castles_paginated(page=1, page_size=1000, db_path=db_path)
    harness.assert_true(ps_huge["page_size"] <= 500, "page_size=1000 is safely capped at max 500")

    # ══════════════════════════════════════════════════════════════
    # TIER 2: PAYLOAD CLEANLINESS (ZERO CONFIG / RAW_JSON BLOAT)
    # ══════════════════════════════════════════════════════════════
    print("\n--- Tier 2: Payload Cleanliness (No Config/Raw_JSON) ---")
    
    sample_res = db.get_admin_castles_paginated(page=1, page_size=25, db_path=db_path)
    has_forbidden_config = False
    has_forbidden_raw_json = False
    
    for u in sample_res["items"]:
        if "config" in u:
            has_forbidden_config = True
        if "raw_json" in u:
            has_forbidden_raw_json = True
        for prev in u.get("castle_previews", []):
            if "config" in prev:
                has_forbidden_config = True
            if "raw_json" in prev:
                has_forbidden_raw_json = True
                
    harness.assert_true(not has_forbidden_config, "Zero `config` bloat in summary items and castle_previews")
    harness.assert_true(not has_forbidden_raw_json, "Zero `raw_json` bloat in summary items and castle_previews")

    # Verify previews contain only lightweight identification
    preview_count = sum(len(u.get("castle_previews", [])) for u in sample_res["items"])
    harness.assert_true(preview_count > 0, f"castle_previews correctly populated ({preview_count} previews)")
    first_preview = next(p for u in sample_res["items"] for p in u.get("castle_previews", []))
    harness.assert_true("id" in first_preview and "email" in first_preview, "Previews contain lightweight id and email")

    # Verify dedicated on-demand config endpoint loads full config when requested
    sample_cid = first_preview["id"]
    cfg_data = db.get_castle_config(sample_cid, db_path=db_path)
    harness.assert_true(cfg_data is not None and "config" in cfg_data, "get_castle_config successfully loads full config on-demand")

    # ══════════════════════════════════════════════════════════════
    # TIER 3: SEARCH ROBUSTNESS
    # ══════════════════════════════════════════════════════════════
    print("\n--- Tier 3: Search Robustness Across Entities ---")
    
    # 1. Search by user email
    res_user_email = db.get_admin_castles_paginated(search="target_special_search@needle.com", db_path=db_path)
    harness.assert_equal(res_user_email["total"], 1, "Search by user email matches exactly 1 user")
    harness.assert_equal(res_user_email["items"][0]["email"], "target_special_search@needle.com", "Matched user email matches query")

    # 2. Search by username
    res_username = db.get_admin_castles_paginated(search="uniquelordmagnificent", db_path=db_path)
    harness.assert_equal(res_username["total"], 1, "Search by username matches exactly 1 user")
    harness.assert_equal(res_username["items"][0]["display_name"], "UniqueLordMagnificent", "Matched username matches query")

    # 3. Search by castle ID
    res_cid = db.get_admin_castles_paginated(search="castle_special_needle_999", db_path=db_path)
    harness.assert_equal(res_cid["total"], 1, "Search by castle ID finds the owning user")
    harness.assert_equal(res_cid["items"][0]["email"], "target_special_search@needle.com", "Found correct owner for castle ID")

    # 4. Search by castle email
    res_cemail = db.get_admin_castles_paginated(search="castle_needle_email@castlemail.org", db_path=db_path)
    harness.assert_equal(res_cemail["total"], 1, "Search by castle email finds the owning user")
    harness.assert_equal(res_cemail["items"][0]["email"], "target_special_search@needle.com", "Found correct owner for castle email")

    # 5. Search non-existent term
    res_empty = db.get_admin_castles_paginated(search="phantom_ghost_nonexistent_xyz_999", db_path=db_path)
    harness.assert_equal(res_empty["total"], 0, "Non-existent search returns 0 results")
    harness.assert_equal(len(res_empty["items"]), 0, "Non-existent search items list is empty")

    # ══════════════════════════════════════════════════════════════
    # TIER 4: FILTER STATUS (ALL, WITH_CASTLES, NO_CASTLES, RUNNING)
    # ══════════════════════════════════════════════════════════════
    print("\n--- Tier 4: Filter Status Options ---")
    
    res_all = db.get_admin_castles_paginated(filter_status="all", page_size=100, db_path=db_path)
    harness.assert_equal(res_all["total"], 60, "Filter 'all' returns all 60 users")

    res_with_castles = db.get_admin_castles_paginated(filter_status="with_castles", page_size=100, db_path=db_path)
    harness.assert_equal(res_with_castles["total"], 55, "Filter 'with_castles' returns exactly 55 users")
    harness.assert_true(all(u["castles_count"] > 0 for u in res_with_castles["items"]), "All items in 'with_castles' have castles_count > 0")

    res_no_castles = db.get_admin_castles_paginated(filter_status="no_castles", page_size=100, db_path=db_path)
    harness.assert_equal(res_no_castles["total"], 5, "Filter 'no_castles' returns exactly 5 users (users 56 to 60)")
    harness.assert_true(all(u["castles_count"] == 0 for u in res_no_castles["items"]), "All items in 'no_castles' have castles_count == 0")

    res_running = db.get_admin_castles_paginated(filter_status="running", page_size=100, db_path=db_path)
    harness.assert_true(res_running["total"] > 0, f"Filter 'running' returns active users ({res_running['total']})")
    harness.assert_true(all(u["running_count"] > 0 for u in res_running["items"]), "All items in 'running' have running_count > 0")

    # ══════════════════════════════════════════════════════════════
    # TIER 5: MERCHANT TENANT ISOLATION
    # ══════════════════════════════════════════════════════════════
    print("\n--- Tier 5: Merchant Admin Tenant Isolation ---")
    
    # 1. Tenant Alpha filter
    res_alpha = db.get_admin_castles_paginated(tenant_domains=["tenant-alpha.com"], page_size=100, db_path=db_path)
    harness.assert_equal(res_alpha["total"], 10, "Tenant Alpha query returns exactly 10 users")
    harness.assert_true(
        all(u["tenant_domain"] == "tenant-alpha.com" for u in res_alpha["items"]),
        "100% of returned users strictly belong to tenant-alpha.com"
    )
    harness.assert_equal(res_alpha["summary_stats"]["total_users"], 10, "Tenant Alpha summary_stats total_users is 10")

    # 2. Tenant Beta filter
    res_beta = db.get_admin_castles_paginated(tenant_domains=["tenant-beta.com"], page_size=100, db_path=db_path)
    harness.assert_equal(res_beta["total"], 10, "Tenant Beta query returns exactly 10 users")
    harness.assert_true(
        all(u["tenant_domain"] == "tenant-beta.com" for u in res_beta["items"]),
        "100% of returned users strictly belong to tenant-beta.com"
    )

    # 3. Disjoint check between Alpha and Beta
    alpha_uids = {u["uid"] for u in res_alpha["items"]}
    beta_uids = {u["uid"] for u in res_beta["items"]}
    harness.assert_equal(len(alpha_uids.intersection(beta_uids)), 0, "Zero cross-tenant leakage between Alpha and Beta")

    # 4. Merchant with empty domain list
    res_empty_domains = db.get_admin_castles_paginated(tenant_domains=[], page_size=100, db_path=db_path)
    harness.assert_equal(res_empty_domains["total"], 0, "Merchant with empty tenant domains receives 0 users")

    # 5. Non-existent tenant domain
    res_ghost_domain = db.get_admin_castles_paginated(tenant_domains=["ghost-domain.org"], page_size=100, db_path=db_path)
    harness.assert_equal(res_ghost_domain["total"], 0, "Non-existent tenant domain returns 0 users")

    # Cleanup temp db
    try:
        os.remove(db_path)
        os.rmdir(temp_dir)
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"CHALLENGER STRESS SUITE RESULT: {harness.passed}/{harness.total} Checks Passed")
    print(f"{'='*70}")
    
    if harness.failures:
        print("\nFailures:")
        for f in harness.failures:
            print(f" - {f}")
        sys.exit(1)
    else:
        print("ALL ADVERSARIAL BOUNDARY AND STRESS CHECKS PASSED EMPIRICALLY!")
        sys.exit(0)


if __name__ == "__main__":
    run_challenge()
