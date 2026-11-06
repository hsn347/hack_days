// @ts-check
/**
 * tools/stress_m4_sanitization.mjs
 * ══════════════════════════════════════════════════════════════════════════════════════
 * Milestone 4 Empirical Challenge: Stress Testing Logout & Account Switch Sanitization.
 * Tests:
 * 1. Multi-user castle caches & legacy prefixes purging.
 * 2. Active castle key deletion.
 * 3. Auth profiles and session token removal across localStorage and sessionStorage.
 * 4. UI preference preservation (osmanli_lang, osmanli_theme).
 * 5. Complete isolation during rapid account switching (User A -> User B).
 * 6. High-volume stress (1,000 interleaved keys) to detect index-shifting bugs.
 * 7. In-memory TanStack QueryClient cache purging.
 * ══════════════════════════════════════════════════════════════════════════════════════
 */

import { performance } from 'perf_hooks';

class MockStorage {
  constructor() {
    /** @type {Map<string, string>} */
    this._map = new Map();
  }

  getItem(key) {
    return this._map.has(key) ? this._map.get(key) : null;
  }

  setItem(key, value) {
    this._map.set(String(key), String(value));
  }

  removeItem(key) {
    this._map.delete(String(key));
  }

  clear() {
    this._map.clear();
  }

  key(index) {
    const keys = Array.from(this._map.keys());
    return index >= 0 && index < keys.length ? keys[index] : null;
  }

  get length() {
    return this._map.size;
  }

  // Helper for test assertions
  getAllKeys() {
    return Array.from(this._map.keys());
  }

  dump() {
    return Object.fromEntries(this._map);
  }
}

class MockQueryClient {
  constructor() {
    this.queries = new Map();
    this.mutations = new Map();
  }

  setQueryData(key, data) {
    this.queries.set(JSON.stringify(key), data);
  }

  getQueryData(key) {
    return this.queries.get(JSON.stringify(key));
  }

  clear() {
    this.queries.clear();
    this.mutations.clear();
  }

  size() {
    return this.queries.size + this.mutations.size;
  }
}

// Emulate implementation of purgeCastlesCache from useCastles.ts
function runPurgeCastlesCache(storage, userId) {
  const CASTLES_CACHE_PREFIX = 'empire_castles_cache_';
  const LEGACY_CASTLES_CACHE_PREFIX = 'ibra_castles_cache_';
  const ACTIVE_CASTLE_PREFIX = 'empire_active_castle_';
  const LEGACY_ACTIVE_CASTLE_PREFIX = 'ibra_active_castle_';

  if (userId) {
    storage.removeItem(`${CASTLES_CACHE_PREFIX}${userId}`);
    storage.removeItem(`${LEGACY_CASTLES_CACHE_PREFIX}${userId}`);
    storage.removeItem(`${ACTIVE_CASTLE_PREFIX}${userId}`);
    storage.removeItem(`${LEGACY_ACTIVE_CASTLE_PREFIX}${userId}`);
  }

  const keysToRemove = [];
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i);
    if (
      key &&
      (key.startsWith(CASTLES_CACHE_PREFIX) ||
        key.startsWith(LEGACY_CASTLES_CACHE_PREFIX) ||
        key.startsWith(ACTIVE_CASTLE_PREFIX) ||
        key.startsWith(LEGACY_ACTIVE_CASTLE_PREFIX))
    ) {
      keysToRemove.push(key);
    }
  }

  for (const key of keysToRemove) {
    storage.removeItem(key);
  }
}

// Emulate implementation of purgeUserDataOnLogout from useAuth.ts
function runPurgeUserDataOnLogout(localStorage, sessionStorage, queryClient, userId) {
  // 1. Purge memory cache completely
  if (queryClient) {
    queryClient.clear();
  }

  // 2. Clear user profile cache from localStorage
  localStorage.removeItem('ibra_auth_profile');
  localStorage.removeItem('empire_auth_profile');

  // 3. Purge all castle caches & active castle selection
  runPurgeCastlesCache(localStorage, userId);

  // 4. Scan and remove any residual user-specific keys matching cache patterns
  const keysToRemove = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key) continue;
    if (
      key.startsWith('empire_castles_cache_') ||
      key.startsWith('ibra_castles_cache_') ||
      key.startsWith('empire_active_castle_') ||
      key.startsWith('ibra_active_castle_') ||
      key.startsWith('empire_auth_profile_') ||
      key.startsWith('ibra_auth_profile_') ||
      key === 'ibra_auth_profile' ||
      key === 'empire_auth_profile' ||
      key === 'osmanli_admin_session_token'
    ) {
      keysToRemove.push(key);
    }
  }

  if (userId) {
    keysToRemove.push(`empire_castles_cache_${userId}`);
    keysToRemove.push(`ibra_castles_cache_${userId}`);
    keysToRemove.push(`empire_active_castle_${userId}`);
    keysToRemove.push(`ibra_active_castle_${userId}`);
  }

  for (const key of keysToRemove) {
    localStorage.removeItem(key);
  }

  // 5. Clear session storage
  if (sessionStorage) {
    sessionStorage.removeItem('osmanli_admin_session_token');
  }
}

// ─── Test Harness ────────────────────────────────────────────────────────────
class StressHarness {
  constructor() {
    this.passed = 0;
    this.failed = 0;
    this.failures = [];
  }

  assert(condition, message) {
    if (condition) {
      this.passed++;
      console.log(`  [PASS] ${message}`);
    } else {
      this.failed++;
      this.failures.push(message);
      console.error(`  [FAIL] ${message}`);
    }
  }
}

async function runAllStressTests() {
  const harness = new StressHarness();
  const startTime = performance.now();

  console.log('═'.repeat(78));
  console.log('CHALLENGER M4: EMPIRICAL STRESS TEST HARNESS — LOGOUT SANITIZATION');
  console.log(`Execution Time: ${new Date().toISOString()}`);
  console.log('═'.repeat(78));

  // ───────────────────────────────────────────────────────────────────────────
  // Suite 1: Multi-User & Legacy Prefix Storage Sanitization
  // ───────────────────────────────────────────────────────────────────────────
  console.log('\n--- Suite 1: Multi-User & Legacy Storage Sanitization ---');
  {
    const local = new MockStorage();
    const session = new MockStorage();
    const qc = new MockQueryClient();

    // Setup multi-user castle caches
    local.setItem('empire_castles_cache_user1', JSON.stringify({ items: [{ id: 101, name: 'C1' }] }));
    local.setItem('empire_castles_cache_user2', JSON.stringify({ items: [{ id: 202, name: 'C2' }] }));
    local.setItem('ibra_castles_cache_legacy', JSON.stringify({ items: [{ id: 303, name: 'Legacy' }] }));
    local.setItem('empire_active_castle_user1', '101');
    local.setItem('ibra_active_castle_legacy', '303');
    local.setItem('empire_auth_profile', JSON.stringify({ uid: 'user1', email: 'u1@osmanli.com' }));
    local.setItem('ibra_auth_profile', JSON.stringify({ uid: 'user1', email: 'u1@osmanli.com' }));
    local.setItem('ibra_auth_profile_main', JSON.stringify({ uid: 'user1', email: 'u1@osmanli.com' }));
    local.setItem('empire_auth_profile_tenant2', JSON.stringify({ uid: 'user2', email: 'u2@osmanli.com' }));
    local.setItem('osmanli_admin_session_token', 'admin_secret_999');
    session.setItem('osmanli_admin_session_token', 'session_admin_secret_999');

    // Safe UI preferences
    local.setItem('osmanli_lang', 'ar');
    local.setItem('osmanli_theme', 'dark');
    local.setItem('user_table_page_size', '25');

    // Query Client state
    qc.setQueryData(['castles', 'user1'], [{ id: 101 }]);
    qc.setQueryData(['castle', 'user1', '101'], { id: 101, details: 'secret' });
    qc.setQueryData(['admin_stats'], { total: 10 });

    harness.assert(local.length === 13, 'Setup: 13 keys populated in localStorage');
    harness.assert(session.length === 1, 'Setup: 1 key in sessionStorage');
    harness.assert(qc.size() === 3, 'Setup: 3 queries in QueryClient');

    // Execute purge
    runPurgeUserDataOnLogout(local, session, qc, 'user1');

    // Assert zero sensitive residuals
    const remainingKeys = local.getAllKeys();
    const sensitiveKeys = remainingKeys.filter(
      k =>
        k.includes('castles_cache') ||
        k.includes('active_castle') ||
        k.includes('auth_profile') ||
        k.includes('session_token') ||
        k.includes('user1') ||
        k.includes('user2') ||
        k.includes('legacy')
    );

    harness.assert(
      sensitiveKeys.length === 0,
      `Purge eliminates 100% of sensitive keys (found: ${JSON.stringify(sensitiveKeys)})`
    );
    harness.assert(
      local.getItem('empire_castles_cache_user1') === null,
      'empire_castles_cache_user1 is completely removed'
    );
    harness.assert(
      local.getItem('ibra_castles_cache_legacy') === null,
      'ibra_castles_cache_legacy is completely removed'
    );
    harness.assert(
      local.getItem('empire_active_castle_user1') === null,
      'empire_active_castle_user1 is completely removed'
    );
    harness.assert(
      local.getItem('ibra_active_castle_legacy') === null,
      'ibra_active_castle_legacy is completely removed'
    );
    harness.assert(
      local.getItem('osmanli_admin_session_token') === null,
      'osmanli_admin_session_token is wiped from localStorage'
    );
    harness.assert(
      session.getItem('osmanli_admin_session_token') === null,
      'osmanli_admin_session_token is wiped from sessionStorage'
    );

    // Assert UI settings preserved
    harness.assert(local.getItem('osmanli_lang') === 'ar', 'UI preference osmanli_lang preserved');
    harness.assert(local.getItem('osmanli_theme') === 'dark', 'UI preference osmanli_theme preserved');
    harness.assert(
      local.getItem('user_table_page_size') === '25',
      'UI preference user_table_page_size preserved'
    );

    // Assert QueryClient purged
    harness.assert(qc.size() === 0, 'QueryClient memory cache is completely emptied (0 queries)');
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Suite 2: Account Switch Isolation (User A -> User B)
  // ───────────────────────────────────────────────────────────────────────────
  console.log('\n--- Suite 2: Account Switch Isolation ---');
  {
    const local = new MockStorage();
    const session = new MockStorage();
    const qc = new MockQueryClient();

    // User A logs in and uses the app
    const userA = 'uid_alice_777';
    local.setItem(`empire_castles_cache_${userA}`, JSON.stringify({ items: [{ id: 1, name: "Alice's Fortress" }] }));
    local.setItem(`empire_active_castle_${userA}`, '1');
    local.setItem('empire_auth_profile', JSON.stringify({ uid: userA, email: 'alice@empire.com' }));
    qc.setQueryData(['castles', userA], [{ id: 1 }]);

    // Now switchAccount('bob@empire.com') triggers purgeUserDataOnLogout(userA)
    runPurgeUserDataOnLogout(local, session, qc, userA);

    // Verify User A data is 100% gone before User B state is mounted
    const intermediateKeys = local.getAllKeys();
    harness.assert(
      !intermediateKeys.some(k => k.includes(userA)),
      'Account switch: User A data is 100% eliminated before User B initialization'
    );
    harness.assert(qc.size() === 0, 'Account switch: Query cache cleared before User B loads');

    // Now User B state is loaded
    const userB = 'uid_bob_888';
    local.setItem(`empire_castles_cache_${userB}`, JSON.stringify({ items: [{ id: 99, name: "Bob's Bastion" }] }));
    local.setItem(`empire_active_castle_${userB}`, '99');
    local.setItem('empire_auth_profile', JSON.stringify({ uid: userB, email: 'bob@empire.com' }));
    qc.setQueryData(['castles', userB], [{ id: 99 }]);

    // Assert User B sees only their data
    harness.assert(
      local.getItem(`empire_castles_cache_${userA}`) === null,
      'User B session cannot access User A castle cache'
    );
    harness.assert(
      local.getItem(`empire_active_castle_${userA}`) === null,
      'User B session cannot access User A active castle'
    );
    harness.assert(
      local.getItem(`empire_castles_cache_${userB}`) !== null,
      'User B castle cache is correctly intact'
    );
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Suite 3: Generic Logout without explicit userId argument
  // ───────────────────────────────────────────────────────────────────────────
  console.log('\n--- Suite 3: Generic Logout Purge (No userId argument) ---');
  {
    const local = new MockStorage();
    const session = new MockStorage();
    const qc = new MockQueryClient();

    // Populate orphaned keys from multiple users
    local.setItem('empire_castles_cache_orphanA', 'dataA');
    local.setItem('empire_castles_cache_orphanB', 'dataB');
    local.setItem('ibra_castles_cache_orphanC', 'dataC');
    local.setItem('empire_active_castle_orphanA', 'castleA');
    local.setItem('ibra_active_castle_orphanC', 'castleC');
    local.setItem('empire_auth_profile_tenant_x', 'profileX');
    local.setItem('ibra_auth_profile_main', 'profileMain');
    local.setItem('osmanli_lang', 'en');

    // Call purgeUserDataOnLogout() with undefined userId
    runPurgeUserDataOnLogout(local, session, qc, undefined);

    const remainingKeys = local.getAllKeys();
    harness.assert(
      remainingKeys.length === 1 && remainingKeys[0] === 'osmanli_lang',
      `Generic purge wipes all castle/auth keys even without userId (remaining: ${JSON.stringify(remainingKeys)})`
    );
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Suite 4: High-Volume Adversarial Stress (1,000 interleaved keys)
  // ───────────────────────────────────────────────────────────────────────────
  console.log('\n--- Suite 4: High-Volume Stress Test (1,000 interleaved keys) ---');
  {
    const local = new MockStorage();
    const session = new MockStorage();
    const qc = new MockQueryClient();

    const TOTAL_KEYS = 1000;
    let expectedPurgedCount = 0;
    let expectedRetainedCount = 0;

    for (let i = 0; i < TOTAL_KEYS; i++) {
      if (i % 2 === 0) {
        // Sensitive key (should be purged)
        const prefixes = [
          'empire_castles_cache_',
          'ibra_castles_cache_',
          'empire_active_castle_',
          'ibra_active_castle_',
          'empire_auth_profile_',
          'ibra_auth_profile_',
        ];
        const prefix = prefixes[i % prefixes.length];
        local.setItem(`${prefix}usr_${i}`, `sensitive_payload_${i}`);
        expectedPurgedCount++;
      } else {
        // Safe UI / app key (should be retained)
        local.setItem(`ui_config_pref_${i}`, `safe_setting_${i}`);
        expectedRetainedCount++;
      }
    }

    harness.assert(
      local.length === TOTAL_KEYS,
      `Setup: Successfully populated ${TOTAL_KEYS} interleaved keys (${expectedPurgedCount} sensitive, ${expectedRetainedCount} safe)`
    );

    const purgeStart = performance.now();
    runPurgeUserDataOnLogout(local, session, qc, 'usr_0');
    const purgeDurationMs = performance.now() - purgeStart;

    harness.assert(
      local.length === expectedRetainedCount,
      `High-volume purge left exactly ${expectedRetainedCount} safe keys (no keys skipped due to index shift)`
    );

    const remainingKeys = local.getAllKeys();
    const leakedKeys = remainingKeys.filter(
      k =>
        k.startsWith('empire_castles_cache_') ||
        k.startsWith('ibra_castles_cache_') ||
        k.startsWith('empire_active_castle_') ||
        k.startsWith('ibra_active_castle_') ||
        k.startsWith('empire_auth_profile_') ||
        k.startsWith('ibra_auth_profile_')
    );

    harness.assert(
      leakedKeys.length === 0,
      `Zero leaks detected across 1,000 keys (purged in ${purgeDurationMs.toFixed(2)}ms)`
    );
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Suite 5: Exact W3C Storage Index Mutability Verification
  // ───────────────────────────────────────────────────────────────────────────
  console.log('\n--- Suite 5: W3C Key Iteration Robustness ---');
  {
    // Verify that iterating keys does not skip entries even in environments where
    // storage.key(i) dynamically shifts as entries are collected.
    // In our implementation, keys are collected into a separate Array before removing,
    // which prevents the classic for(i=0; i<length; i++) { removeItem } bug.
    const local = new MockStorage();
    local.setItem('empire_castles_cache_k1', 'v1');
    local.setItem('empire_castles_cache_k2', 'v2');
    local.setItem('empire_castles_cache_k3', 'v3');
    local.setItem('empire_castles_cache_k4', 'v4');
    local.setItem('osmanli_lang', 'tr');

    runPurgeUserDataOnLogout(local, null, null, null);

    harness.assert(
      local.length === 1 && local.getItem('osmanli_lang') === 'tr',
      'Consecutive matching keys are all removed without index-skipping'
    );
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Results Summary
  // ───────────────────────────────────────────────────────────────────────────
  const totalElapsed = (performance.now() - startTime).toFixed(2);
  console.log('\n' + '═'.repeat(78));
  console.log(`STRESS TEST SUMMARY: ${harness.passed}/${harness.passed + harness.failed} checks passed (${totalElapsed}ms)`);
  console.log('═'.repeat(78));

  if (harness.failed > 0) {
    console.error('\nFAILURES ENCOUNTERED:');
    for (const failure of harness.failures) {
      console.error(`  - ${failure}`);
    }
    process.exit(1);
  }

  console.log('\n>>> ALL EMPIRICAL SANITIZATION & STRESS TESTS PASSED WITH 100% SUCCESS <<<\n');
  process.exit(0);
}

runAllStressTests().catch(err => {
  console.error('Fatal error in stress test runner:', err);
  process.exit(1);
});
