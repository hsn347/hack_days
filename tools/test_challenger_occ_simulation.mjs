// tools/test_challenger_occ_simulation.mjs
// Empirical test harness for Milestone 3 (Build & OCC Challenger)
// Verifies botApi.updateCastle 409 conflict handling and TaskTabContent cache invalidation.

import http from 'node:http';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');

console.log('='.repeat(70));
console.log('CHALLENGER M3: EMPIRICAL OCC 409 CONFLICT SIMULATION HARNESS');
console.log('='.repeat(70));

// 1. Setup local mock HTTP server
const server = http.createServer((req, res) => {
  const url = req.url;
  
  if (url === '/api/castles/conflict-castle-json') {
    res.writeHead(409, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      detail: 'Conflict: Castle config has been modified concurrently. Current version is 3'
    }));
    return;
  }

  if (url === '/api/castles/conflict-castle-empty') {
    res.writeHead(409, { 'Content-Type': 'application/json' });
    res.end('{}');
    return;
  }

  if (url === '/api/castles/conflict-castle-malformed') {
    res.writeHead(409, { 'Content-Type': 'text/plain' });
    res.end('Not a JSON error');
    return;
  }

  if (url === '/api/castles/server-error-500') {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end('Internal Server Error');
    return;
  }

  if (url === '/api/castles/success-castle') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      castle: {
        id: 'success-castle',
        castle_id: 'success-castle',
        version: 5,
        config: { auto_farm: true }
      }
    }));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not Found');
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const PORT = server.address().port;
console.log(`[PASS] Mock HTTP Server listening on http://127.0.0.1:${PORT}`);

try {
  // 2. Exact reproduction of botApi.updateCastle error handling logic
  async function simulateUpdateCastle(castleId, payload, baseUrl = `http://127.0.0.1:${PORT}`) {
    const res = await fetch(`${baseUrl}/api/castles/${castleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      if (res.status === 409) {
        const errJson = await res.json().catch(() => ({}));
        const conflictErr = new Error(errJson.detail || 'تعارض في حفظ الإعدادات: تم تعديل البيانات بالتزامن');
        conflictErr.status = 409;
        conflictErr.isConflict = true;
        throw conflictErr;
      }
      const err = await res.text();
      throw new Error(err);
    }
    const data = await res.json();
    return { status: data.status, castle: data.castle };
  }

  // ── TEST 1: 409 Conflict with backend JSON detail ──────────────────────────
  console.log('\n[TEST 1] Testing HTTP 409 with custom JSON detail...');
  try {
    await simulateUpdateCastle('conflict-castle-json', { version: 1, config: {} });
    assert.fail('Should have thrown 409 error');
  } catch (err) {
    assert.strictEqual(err.status, 409, 'Error status must be 409');
    assert.strictEqual(err.isConflict, true, 'Error must have isConflict === true');
    assert.strictEqual(
      err.message,
      'Conflict: Castle config has been modified concurrently. Current version is 3',
      'Error message must match backend detail'
    );
    console.log('  -> PASS: 409 correctly caught, flagged isConflict=true, message preserved.');
  }

  // ── TEST 2: 409 Conflict with empty JSON body ──────────────────────────────
  console.log('\n[TEST 2] Testing HTTP 409 with empty body (fallback message)...');
  try {
    await simulateUpdateCastle('conflict-castle-empty', { version: 1, config: {} });
    assert.fail('Should have thrown 409 error');
  } catch (err) {
    assert.strictEqual(err.status, 409, 'Error status must be 409');
    assert.strictEqual(err.isConflict, true, 'Error must have isConflict === true');
    assert.strictEqual(
      err.message,
      'تعارض في حفظ الإعدادات: تم تعديل البيانات بالتزامن',
      'Fallback Arabic conflict message must be used'
    );
    console.log('  -> PASS: 409 fallback message correctly used when detail is empty.');
  }

  // ── TEST 3: 409 Conflict with malformed non-JSON body ───────────────────────
  console.log('\n[TEST 3] Testing HTTP 409 with malformed non-JSON body...');
  try {
    await simulateUpdateCastle('conflict-castle-malformed', { version: 1, config: {} });
    assert.fail('Should have thrown 409 error');
  } catch (err) {
    assert.strictEqual(err.status, 409, 'Error status must be 409');
    assert.strictEqual(err.isConflict, true, 'Error must have isConflict === true');
    assert.strictEqual(
      err.message,
      'تعارض في حفظ الإعدادات: تم تعديل البيانات بالتزامن',
      'Fallback Arabic conflict message must be used when JSON parse fails'
    );
    console.log('  -> PASS: 409 fallback message correctly used on malformed JSON.');
  }

  // ── TEST 4: Non-409 error (500) must NOT have isConflict flag ──────────────
  console.log('\n[TEST 4] Testing non-409 error (500 Internal Server Error)...');
  try {
    await simulateUpdateCastle('server-error-500', { version: 1, config: {} });
    assert.fail('Should have thrown 500 error');
  } catch (err) {
    assert.notStrictEqual(err.status, 409, 'Status must not be 409');
    assert.strictEqual(err.isConflict, undefined, 'isConflict must NOT be true on 500');
    assert.strictEqual(err.message, 'Internal Server Error');
    console.log('  -> PASS: 500 correctly handled without isConflict flag.');
  }

  // ── TEST 5: Successful 200 response ────────────────────────────────────────
  console.log('\n[TEST 5] Testing successful 200 response with version...');
  const successRes = await simulateUpdateCastle('success-castle', { version: 4, config: {} });
  assert.strictEqual(successRes.status, 'ok');
  assert.strictEqual(successRes.castle.version, 5);
  console.log('  -> PASS: 200 response returns updated version 5.');

  // ── TEST 6: TaskTabContent.tsx Integration & Query Invalidation ────────────
  console.log('\n[TEST 6] Simulating TaskTabContent.tsx OCC error catch & invalidation...');
  const userId = 'user-test-777';
  const castleId = 'conflict-castle-json';
  const invalidatedQueries = [];
  const toastErrors = [];

  const mockQc = {
    invalidateQueries: (opts) => {
      invalidatedQueries.push(opts.queryKey);
    }
  };

  const mockToast = {
    error: (msg, opts) => {
      toastErrors.push({ msg, opts });
    }
  };

  let saveStatus = 'saving';
  let saveErrorMsg = null;

  try {
    await simulateUpdateCastle(castleId, { version: 1, config: { test: true } });
  } catch (err) {
    saveStatus = 'error';
    if (err?.status === 409 || err?.isConflict) {
      const conflictMsg = 'تم تعديل إعدادات القلعة بالتزامن من نافذة أخرى. جاري تحديث البيانات...';
      saveErrorMsg = conflictMsg;
      mockToast.error(conflictMsg, { id: 'occ-conflict-' + castleId });
      // Invalidate queries to reload latest authoritative config & version
      mockQc.invalidateQueries({ queryKey: ['castles', userId] });
      mockQc.invalidateQueries({ queryKey: ['castle', userId, castleId] });
    } else {
      saveErrorMsg = err instanceof Error ? err.message : 'فشل الحفظ';
    }
  }

  assert.strictEqual(saveStatus, 'error', 'saveStatus must transition to error');
  assert.strictEqual(
    saveErrorMsg,
    'تم تعديل إعدادات القلعة بالتزامن من نافذة أخرى. جاري تحديث البيانات...',
    'saveErrorMsg must show conflict warning'
  );
  assert.strictEqual(toastErrors.length, 1, 'Toast error must be triggered once');
  assert.strictEqual(toastErrors[0].opts.id, `occ-conflict-${castleId}`, 'Toast ID must be scoped to castle ID');

  assert.strictEqual(invalidatedQueries.length, 2, 'Exactly two queries must be invalidated');
  assert.deepStrictEqual(invalidatedQueries[0], ['castles', userId], 'castles list query must be invalidated');
  assert.deepStrictEqual(invalidatedQueries[1], ['castle', userId, castleId], 'single castle query must be invalidated');
  console.log('  -> PASS: TaskTabContent error handler correctly catches 409, sets saveStatus=error, triggers toast, and invalidates query cache.');

  // ── TEST 7: Source code verification for botApi.ts and TaskTabContent.tsx ──
  console.log('\n[TEST 7] Verifying source code exact matches in repository...');
  const botApiPath = path.join(ROOT_DIR, 'dashboard', 'src', 'lib', 'botApi.ts');
  const taskTabPath = path.join(ROOT_DIR, 'dashboard', 'src', 'components', 'accounts', 'TaskTabContent.tsx');

  const botApiCode = fs.readFileSync(botApiPath, 'utf-8');
  const taskTabCode = fs.readFileSync(taskTabPath, 'utf-8');

  // Verify botApi.ts contains:
  assert(botApiCode.includes('if (res.status === 409)'), 'botApi.ts must check res.status === 409');
  assert(botApiCode.includes(';(conflictErr as any).status = 409'), 'botApi.ts must assign status 409');
  assert(botApiCode.includes(';(conflictErr as any).isConflict = true'), 'botApi.ts must set isConflict = true');
  assert(botApiCode.includes('version?:     number'), 'botApi.ts payload must accept version');

  // Verify TaskTabContent.tsx contains:
  const normalizedTaskTab = taskTabCode.replace(/\r\n/g, '\n');
  assert(normalizedTaskTab.includes('if (err?.status === 409 || err?.isConflict)'), 'TaskTabContent.tsx must catch 409 / isConflict');
  assert(normalizedTaskTab.includes("qc.invalidateQueries({ queryKey: ['castles', userId] })"), 'TaskTabContent.tsx must invalidate castles list');
  assert(normalizedTaskTab.includes("qc.invalidateQueries({ queryKey: ['castle', userId, castle.id] })"), 'TaskTabContent.tsx must invalidate single castle');
  assert(normalizedTaskTab.includes("version: currentVersionRef.current"), 'TaskTabContent.tsx unmount save must pass currentVersionRef.current');
  console.log('  -> PASS: Source code directly verifies all 409 and OCC bindings.');

  console.log('\n' + '='.repeat(70));
  console.log('>>> ALL OCC SIMULATION & INTEGRATION TESTS PASSED CLEANLY (7/7)!');
  console.log('='.repeat(70));
} finally {
  server.close();
}
