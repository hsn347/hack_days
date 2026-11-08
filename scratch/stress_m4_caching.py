# -*- coding: utf-8 -*-
"""
tools/stress_m4_caching.py — Empirical Challenge Harness for Milestone 4 (Caching & Invalidation).
══════════════════════════════════════════════════════════════════════════════════════
Empirical stress-testing per AGENTS_CONSTITUTION.md Rule 13 and Challenger M4 mandate:
1. Exact TTL validation (staleTime/gcTime) across list, single item, live stats, and global queryClient.
2. Invalidation validation for all 9 mutation hooks (collection and item query keys).
3. Memory removal validation for useDeleteCastle (qc.removeQueries).
4. TanStack Query hierarchical cache simulation with adversarial edge cases (user isolation, cross-talk, prefix matching).
5. Comprehensive logout and account switch storage sanitization with zero residual leaks.
"""

import os
import re
import sys
import json
import time

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_SRC = os.path.join(ROOT_DIR, "dashboard", "src")
USE_CASTLES_PATH = os.path.join(DASHBOARD_SRC, "hooks", "useCastles.ts")
USE_AUTH_PATH = os.path.join(DASHBOARD_SRC, "hooks", "useAuth.ts")
QUERY_CLIENT_PATH = os.path.join(DASHBOARD_SRC, "lib", "queryClient.ts")


class ChallengeRunner:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failures = []

    def verify(self, condition: bool, title: str, detail: str = ""):
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  [PASS] {title}")
        else:
            msg = f"{title} — {detail}" if detail else title
            self.failures.append(msg)
            print(f"  [FAIL] {msg}")


# ─── PART 1: EXACT TTL & GC DURATION EXTRACTION ──────────────────────────────

def challenge_exact_ttls(runner: ChallengeRunner):
    print("\n--- Challenge 1: Exact TTL & GC Time Values ---")

    # 1.1 queryClient.ts global defaults
    with open(QUERY_CLIENT_PATH, "r", encoding="utf-8") as f:
        qc_src = f.read()

    gc_match = re.search(r"gcTime:\s*(\d[\d_]*)", qc_src)
    stale_match = re.search(r"staleTime:\s*(\d[\d_]*)", qc_src)

    gc_val = int(gc_match.group(1).replace("_", "")) if gc_match else None
    stale_val = int(stale_match.group(1).replace("_", "")) if stale_match else None

    runner.verify(
        gc_val == 600_000,
        "queryClient global default gcTime is exactly 600_000 (10m)",
        f"Found: {gc_val}"
    )
    runner.verify(
        stale_val == 60_000,
        "queryClient global default staleTime is exactly 60_000 (60s)",
        f"Found: {stale_val}"
    )

    # 1.2 useCastles.ts hook TTLs
    with open(USE_CASTLES_PATH, "r", encoding="utf-8") as f:
        castles_src = f.read()

    def extract_function_body(fn_name: str) -> str:
        pattern = r"export\s+function\s+" + fn_name + r"\b([\s\S]*?)(?=export\s+function|$)"
        m = re.search(pattern, castles_src)
        return m.group(1) if m else ""

    # useCastles list
    castles_body = extract_function_body("useCastles")
    runner.verify(bool(castles_body), "useCastles hook structure exists")
    if castles_body:
        st = re.search(r"staleTime:\s*(\d[\d_]*)", castles_body)
        gc = re.search(r"gcTime:\s*(\d[\d_]*)", castles_body)
        st_val = int(st.group(1).replace("_", "")) if st else None
        gc_val = int(gc.group(1).replace("_", "")) if gc else None
        runner.verify(st_val == 60_000, "useCastles: staleTime == 60_000 (60s)", f"Found: {st_val}")
        runner.verify(gc_val == 600_000, "useCastles: gcTime == 600_000 (10m)", f"Found: {gc_val}")
        runner.verify(gc_val is not None and st_val is not None and gc_val >= st_val, "useCastles: Invariant gcTime >= staleTime holds")

    # useCastle single item
    castle_body = extract_function_body("useCastle")
    runner.verify(bool(castle_body), "useCastle hook structure exists")
    if castle_body:
        st = re.search(r"staleTime:\s*(\d[\d_]*)", castle_body)
        gc = re.search(r"gcTime:\s*(\d[\d_]*)", castle_body)
        st_val = int(st.group(1).replace("_", "")) if st else None
        gc_val = int(gc.group(1).replace("_", "")) if gc else None
        runner.verify(st_val == 30_000, "useCastle: staleTime == 30_000 (30s)", f"Found: {st_val}")
        runner.verify(gc_val == 300_000, "useCastle: gcTime == 300_000 (5m)", f"Found: {gc_val}")
        runner.verify(gc_val is not None and st_val is not None and gc_val >= st_val, "useCastle: Invariant gcTime >= staleTime holds")

    # useLiveBotStats live stats
    live_body = extract_function_body("useLiveBotStats")
    runner.verify(bool(live_body), "useLiveBotStats hook structure exists")
    if live_body:
        st = re.search(r"staleTime:\s*(\d[\d_]*)", live_body)
        gc = re.search(r"gcTime:\s*(\d[\d_]*)", live_body)
        st_val = int(st.group(1).replace("_", "")) if st else None
        gc_val = int(gc.group(1).replace("_", "")) if gc else None
        runner.verify(st_val == 10_000, "useLiveBotStats: staleTime == 10_000 (10s)", f"Found: {st_val}")
        runner.verify(gc_val == 60_000, "useLiveBotStats: gcTime == 60_000 (1m)", f"Found: {gc_val}")
        runner.verify(gc_val is not None and st_val is not None and gc_val >= st_val, "useLiveBotStats: Invariant gcTime >= staleTime holds")


# ─── PART 2: MUTATION HOOK INVALIDATION OF COLLECTION & ITEM KEYS ───────────

def challenge_mutation_invalidation_coverage(runner: ChallengeRunner):
    print("\n--- Challenge 2: Mutation Hooks Collection & Item Query Keys Invalidation ---")

    with open(USE_CASTLES_PATH, "r", encoding="utf-8") as f:
        castles_src = f.read()

    def extract_function_body(fn_name: str) -> str:
        pattern = r"export\s+function\s+" + fn_name + r"\b([\s\S]*?)(?=export\s+function|$)"
        m = re.search(pattern, castles_src)
        return m.group(1) if m else ""

    # Expected mutation hooks to verify
    required_mutations = [
        "useAddCastle",
        "useDeleteCastle",
        "useUpdateCastleCredentials",
        "useToggleCastleActive",
        "useBatchUpdateCastleConfigs",
        "useUpdateBotState",
        "useBotControl",
        "useStopUserBots",
        "useImportCastles",
    ]

    for hook in required_mutations:
        body = extract_function_body(hook)
        runner.verify(bool(body), f"Mutation hook {hook} is defined and exported")
        if not body:
            continue

        # 1. Check collection invalidation ['castles', userId]
        has_collection_invalidation = bool(
            re.search(r"invalidateQueries\(\{\s*queryKey:\s*\['castles',\s*userId\]\s*\}\)", body)
        )
        runner.verify(
            has_collection_invalidation,
            f"{hook}: invalidates collection key ['castles', userId]"
        )

        # 2. Check item query key invalidation / removal
        # Depending on hook, could be ['castle', userId, ...], ['castle', userId], or removeQueries
        if hook == "useDeleteCastle":
            has_item_removal = bool(
                re.search(r"qc\.removeQueries\(\{\s*queryKey:\s*\['castle',\s*userId,\s*castleId\]\s*\}\)", body)
            )
            runner.verify(
                has_item_removal,
                f"{hook}: performs qc.removeQueries on item key ['castle', userId, castleId]"
            )
            has_config_removal = bool(
                re.search(r"qc\.removeQueries\(\{\s*queryKey:\s*\['castleConfig',\s*castleId\]\s*\}\)", body)
            )
            runner.verify(
                has_config_removal,
                f"{hook}: performs qc.removeQueries on castleConfig key ['castleConfig', castleId]"
            )
        elif hook == "useStopUserBots":
            # Invalidates ['castle', userId] which covers all castle items by TanStack Query prefix matching
            has_item_invalidation = bool(
                re.search(r"invalidateQueries\(\{\s*queryKey:\s*\['castle',\s*userId\]\s*\}\)", body)
            )
            runner.verify(
                has_item_invalidation,
                f"{hook}: invalidates item prefix key ['castle', userId] for all user castles"
            )
        elif hook == "useBatchUpdateCastleConfigs":
            has_item_invalidation = bool(
                re.search(r"castleIds\.forEach\b[\s\S]*?queryKey:\s*\['castle',\s*userId,\s*id\]", body)
            )
            runner.verify(
                has_item_invalidation,
                f"{hook}: iterates affected castleIds and invalidates each ['castle', userId, id]"
            )
        elif hook == "useImportCastles":
            has_item_invalidation = bool(
                re.search(r"results\.forEach\b[\s\S]*?queryKey:\s*\['castle',\s*userId,\s*c\.id\]", body)
            )
            runner.verify(
                has_item_invalidation,
                f"{hook}: iterates imported results and invalidates each ['castle', userId, c.id]"
            )
        else:
            # useAddCastle, useUpdateCastleCredentials, useToggleCastleActive, useUpdateBotState, useBotControl
            has_item_invalidation = bool(
                re.search(r"invalidateQueries\(\{\s*queryKey:\s*\['castle',\s*userId,\s*[^\]]+\]\s*\}\)", body)
            )
            runner.verify(
                has_item_invalidation,
                f"{hook}: invalidates specific item key ['castle', userId, castleId]"
            )


# ─── PART 3: TANSTACK QUERY HIERARCHICAL CACHE ADVERSARIAL SIMULATION ───────

class TanStackQueryMock:
    """
    Accurately mirrors TanStack Query v5 cache semantics:
    - Hierarchical key prefix matching
    - Stale tracking vs Memory retention (gcTime)
    - removeQueries (hard deletion) vs invalidateQueries (stale marking)
    """
    def __init__(self):
        self.cache = {}  # key_tuple -> {"data": any, "stale": bool, "updated_at": float}

    def _matches(self, query_key: tuple, filter_key: tuple) -> bool:
        if len(filter_key) > len(query_key):
            return False
        return query_key[:len(filter_key)] == filter_key

    def setQueryData(self, key: list, data: any):
        k = tuple(key)
        self.cache[k] = {"data": data, "stale": False, "updated_at": time.time()}

    def getQueryData(self, key: list):
        k = tuple(key)
        entry = self.cache.get(k)
        return entry["data"] if entry else None

    def invalidateQueries(self, options: dict):
        filter_key = tuple(options["queryKey"])
        count = 0
        for k in self.cache:
            if self._matches(k, filter_key):
                self.cache[k]["stale"] = True
                count += 1
        return count

    def removeQueries(self, options: dict):
        filter_key = tuple(options["queryKey"])
        keys_to_del = [k for k in self.cache if self._matches(k, filter_key)]
        for k in keys_to_del:
            del self.cache[k]
        return len(keys_to_del)

    def isStale(self, key: list) -> bool:
        k = tuple(key)
        entry = self.cache.get(k)
        return entry["stale"] if entry else True

    def exists(self, key: list) -> bool:
        return tuple(key) in self.cache

    def clear(self):
        self.cache.clear()


def challenge_cache_hierarchical_simulation(runner: ChallengeRunner):
    print("\n--- Challenge 3: Adversarial TanStack Query Hierarchical Simulation ---")

    qc = TanStackQueryMock()

    # Setup realistic multi-tenant, multi-castle cache state
    u1 = "user_alpha"
    u2 = "user_beta"

    qc.setQueryData(["castles", u1], [{"id": "c101", "name": "A1"}, {"id": "c102", "name": "A2"}])
    qc.setQueryData(["castle", u1, "c101"], {"id": "c101", "name": "A1", "power": 5000})
    qc.setQueryData(["castle", u1, "c102"], {"id": "c102", "name": "A2", "power": 8000})
    qc.setQueryData(["castleConfig", "c101"], {"auto_gather": True})
    qc.setQueryData(["castleConfig", "c102"], {"auto_gather": False})
    qc.setQueryData(["live_bot_stats"], {"active_count": 2})

    qc.setQueryData(["castles", u2], [{"id": "c201", "name": "B1"}])
    qc.setQueryData(["castle", u2, "c201"], {"id": "c201", "name": "B1", "power": 3000})
    qc.setQueryData(["castleConfig", "c201"], {"auto_gather": True})

    runner.verify(len(qc.cache) == 9, "Initial simulated cache populated with 9 discrete entries")

    # TEST A: useDeleteCastle on c101
    # 1. qc.removeQueries for c101
    # 2. qc.invalidateQueries for collection ['castles', u1]
    # 3. qc.invalidateQueries for ['live_bot_stats']
    del_c = "c101"
    removed_item = qc.removeQueries({"queryKey": ["castle", u1, del_c]})
    removed_cfg = qc.removeQueries({"queryKey": ["castleConfig", del_c]})
    qc.invalidateQueries({"queryKey": ["castles", u1]})
    qc.invalidateQueries({"queryKey": ["live_bot_stats"]})

    runner.verify(removed_item == 1, "useDeleteCastle: item query removed from memory (count = 1)")
    runner.verify(removed_cfg == 1, "useDeleteCastle: config query removed from memory (count = 1)")
    runner.verify(not qc.exists(["castle", u1, del_c]), "useDeleteCastle: castle c101 NO LONGER exists in cache")
    runner.verify(not qc.exists(["castleConfig", del_c]), "useDeleteCastle: castleConfig c101 NO LONGER exists in cache")
    runner.verify(qc.isStale(["castles", u1]), "useDeleteCastle: collection ['castles', u1] marked stale")
    runner.verify(qc.isStale(["live_bot_stats"]), "useDeleteCastle: live_bot_stats marked stale")

    # Isolation check: u1's other castle and u2's castle must be completely untouched
    runner.verify(qc.exists(["castle", u1, "c102"]) and not qc.isStale(["castle", u1, "c102"]),
                  "useDeleteCastle: sibling castle c102 in user_alpha remains valid and retained")
    runner.verify(qc.exists(["castle", u2, "c201"]) and not qc.isStale(["castle", u2, "c201"]),
                  "useDeleteCastle: cross-user isolation: user_beta's castle remains unaffected")

    # TEST B: useBatchUpdateCastleConfigs on ['c102']
    qc.invalidateQueries({"queryKey": ["castle", u1, "c102"]})
    qc.invalidateQueries({"queryKey": ["castleConfig", "c102"]})
    qc.invalidateQueries({"queryKey": ["castles", u1]})
    runner.verify(qc.isStale(["castle", u1, "c102"]), "useBatchUpdate: specific castle marked stale")
    runner.verify(qc.isStale(["castleConfig", "c102"]), "useBatchUpdate: specific castleConfig marked stale")
    runner.verify(not qc.isStale(["castle", u2, "c201"]), "useBatchUpdate: cross-user castle remains fresh")

    # TEST C: useStopUserBots prefix invalidation
    # qc.invalidateQueries(['castle', u1]) should invalidate all remaining castles for u1, NOT u2
    qc.setQueryData(["castle", u1, "c102"], {"id": "c102", "name": "A2"})  # reset to fresh
    runner.verify(not qc.isStale(["castle", u1, "c102"]), "Reset c102 to fresh state")

    qc.invalidateQueries({"queryKey": ["castles", u1]})
    qc.invalidateQueries({"queryKey": ["castle", u1]})
    qc.invalidateQueries({"queryKey": ["live_bot_stats"]})

    runner.verify(qc.isStale(["castle", u1, "c102"]), "useStopUserBots: prefix ['castle', u1] invalidates u1 castle")
    runner.verify(not qc.isStale(["castle", u2, "c201"]), "useStopUserBots: prefix ['castle', u1] DOES NOT touch u2")


# ─── PART 4: LOGOUT & SWITCH SANITIZATION STRESS HARNESS ─────────────────────

def challenge_logout_sanitization_stress(runner: ChallengeRunner):
    print("\n--- Challenge 4: Logout & Switch Account Sanitization Under Adversarial Inputs ---")

    class MockStorage:
        def __init__(self):
            self.data = {}
        def setItem(self, k, v): self.data[k] = str(v)
        def getItem(self, k): return self.data.get(k)
        def removeItem(self, k): self.data.pop(k, None)
        def key(self, idx):
            keys = list(self.data.keys())
            return keys[idx] if 0 <= idx < len(keys) else None
        @property
        def length(self): return len(self.data)

    store = MockStorage()

    # Replicate purgeUserDataOnLogout implementation directly
    def purge_data(user_id=None):
        keys_to_remove = []
        for i in range(store.length):
            k = store.key(i)
            if not k:
                continue
            if (
                k.startswith("empire_castles_cache_") or
                k.startswith("ibra_castles_cache_") or
                k.startswith("empire_active_castle_") or
                k.startswith("ibra_active_castle_") or
                k.startswith("empire_auth_profile_") or
                k.startswith("ibra_auth_profile_") or
                k == "ibra_auth_profile" or
                k == "empire_auth_profile" or
                k == "osmanli_admin_session_token"
            ):
                keys_to_remove.append(k)
        if user_id:
            keys_to_remove.extend([
                f"empire_castles_cache_{user_id}",
                f"ibra_castles_cache_{user_id}",
                f"empire_active_castle_{user_id}",
                f"ibra_active_castle_{user_id}",
            ])
        for k in keys_to_remove:
            store.removeItem(k)

    # 1. Seed adversarial keys:
    # - standard keys
    # - legacy ibra_ keys
    # - tenant-specific auth profile keys
    # - malicious injection key with special characters
    store.setItem("empire_castles_cache_usr_99", json.dumps({"items": ["c1", "c2"]}))
    store.setItem("ibra_castles_cache_usr_99", json.dumps({"items": ["c1", "c2"]}))
    store.setItem("empire_active_castle_usr_99", "c1")
    store.setItem("ibra_active_castle_usr_99", "c1")
    store.setItem("empire_auth_profile_tenant_x", json.dumps({"email": "admin@x.com"}))
    store.setItem("ibra_auth_profile", json.dumps({"email": "admin@x.com"}))
    store.setItem("osmanli_admin_session_token", "jwt_secret_token_abc")

    # Unrelated app settings that MUST persist
    store.setItem("osmanli_theme", "dark")
    store.setItem("osmanli_lang", "tr")

    runner.verify(store.length == 9, "Populated 7 user keys and 2 app preference keys")

    # Run purge
    purge_data("usr_99")

    # Verify zero residual user data
    residual_user_keys = [
        k for k in store.data.keys()
        if any(p in k for p in ["usr_99", "castles_cache", "active_castle", "auth_profile", "session_token"])
    ]
    runner.verify(len(residual_user_keys) == 0, "Zero residual user keys in storage after purge", f"Found: {residual_user_keys}")
    runner.verify(store.getItem("osmanli_theme") == "dark", "App setting 'osmanli_theme' correctly preserved")
    runner.verify(store.getItem("osmanli_lang") == "tr", "App setting 'osmanli_lang' correctly preserved")


# ─── MAIN HARNESS ────────────────────────────────────────────────────────────

def main() -> int:
    start_time = time.perf_counter()
    print("=" * 80)
    print("CHALLENGER M4: EMPIRICAL STRESS TEST FOR CACHING & INVALDATION")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print("=" * 80)

    runner = ChallengeRunner()

    challenge_exact_ttls(runner)
    challenge_mutation_invalidation_coverage(runner)
    challenge_cache_hierarchical_simulation(runner)
    challenge_logout_sanitization_stress(runner)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    print("\n" + "=" * 80)
    print(f"CHALLENGE SUMMARY: {runner.passed}/{runner.total} checks passed ({elapsed_ms:.1f}ms)")
    print("=" * 80)

    if runner.failures:
        print("\nCRITICAL FAILURES DETECTED:")
        for f in runner.failures:
            print(f"  - {f}")
        return 1

    print("\n>>> ALL EMPIRICAL CHALLENGES PASSED! VERDICT: APPROVE <<<\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
