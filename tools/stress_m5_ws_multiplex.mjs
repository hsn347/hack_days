// tools/stress_m5_ws_multiplex.mjs — Empirical Stress Test Suite for Node.js
// Tests JavaScript WebSocket Multiplexer, Reference Counting, Grace Periods, and Teardown.

import assert from 'node:assert'

class MockWebSocket {
  static all = []
  static active = new Set()

  constructor(url) {
    this.url = url
    this.readyState = 1 // OPEN
    this.closed = false
    this.onopen = null
    this.onmessage = null
    this.onclose = null
    this.onerror = null

    MockWebSocket.all.push(this)
    MockWebSocket.active.add(this)
  }

  sendServerMessage(data) {
    if (this.readyState === 1 && this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) })
    }
  }

  close() {
    if (this.closed) return
    this.closed = true
    this.readyState = 3 // CLOSED
    MockWebSocket.active.delete(this)
    if (this.onclose) this.onclose()
  }
}

// Global registry & Multiplexer mirroring useUserBotStatuses.ts
const multiplexers = new Map()

class UserStatusMultiplexer {
  constructor(userId) {
    this.userId = userId
    this.ws = null
    this.listeners = new Set()
    this.latestStatuses = {}
    this.reconnectTimer = null
    this.graceTimer = null
    this.reconnectDelay = 2000
    this.isDestroyed = false
  }

  subscribe(listener) {
    if (this.graceTimer) {
      clearTimeout(this.graceTimer)
      this.graceTimer = null
    }

    this.listeners.add(listener)

    if (Object.keys(this.latestStatuses).length > 0) {
      listener(this.latestStatuses)
    }

    if (!this.ws || this.ws.readyState === 3 || this.ws.readyState === 2) {
      this.connect()
    }

    return () => {
      this.listeners.delete(listener)
      if (this.listeners.size === 0) {
        this.graceTimer = setTimeout(() => {
          this.disconnect()
          multiplexers.delete(this.userId)
        }, 150) // 150ms for swift deterministic test execution
      }
    }
  }

  getStatus(castleId) {
    return this.latestStatuses[castleId]
  }

  getSnapshot() {
    return { ...this.latestStatuses }
  }

  connect() {
    if (this.isDestroyed || !this.userId) return

    this.ws = new MockWebSocket(`ws://localhost:8000/ws/user-status/${this.userId}`)

    this.ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data)
        if (parsed && typeof parsed === 'object') {
          this.latestStatuses = { ...this.latestStatuses, ...parsed }
          this.notify()
        }
      } catch {}
    }

    this.ws.onclose = () => {
      if (!this.isDestroyed && this.listeners.size > 0) {
        this.scheduleReconnect()
      }
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectDelay)
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 10000)
  }

  notify() {
    const snapshot = this.getSnapshot()
    for (const listener of this.listeners) {
      try {
        listener(snapshot)
      } catch {}
    }
  }

  disconnect() {
    this.isDestroyed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.graceTimer) {
      clearTimeout(this.graceTimer)
      this.graceTimer = null
    }
    if (this.ws) {
      try {
        this.ws.close()
      } catch {}
      this.ws = null
    }
  }
}

function getOrCreateMultiplexer(userId) {
  let m = multiplexers.get(userId)
  if (!m) {
    m = new UserStatusMultiplexer(userId)
    multiplexers.set(userId, m)
  }
  return m
}

function purgeAllUserStatusSockets() {
  for (const [, m] of multiplexers) {
    m.disconnect()
  }
  multiplexers.clear()
}

async function runTests() {
  console.log('='.repeat(78))
  console.log('Osmanli Dashboard — Node.js WebSocket Multiplexer Stress Test')
  console.log('='.repeat(78))

  // Test 1: 50 Card Concurrency
  console.log('\n--- Suite 1: Mounting 50 Cards Concurrently ---')
  const userA = 'user_node_50_cards'
  const unsubsA = []
  let notifyCountA = 0

  for (let i = 0; i < 50; i++) {
    const mux = getOrCreateMultiplexer(userA)
    const unsub = mux.subscribe((s) => {
      notifyCountA++
    })
    unsubsA.push(unsub)
  }

  assert.strictEqual(MockWebSocket.all.length, 1, 'Exactly 1 WebSocket opened for 50 cards')
  assert.strictEqual(MockWebSocket.active.size, 1, 'Exactly 1 active WebSocket connection in pool')
  assert.strictEqual(multiplexers.get(userA).listeners.size, 50, 'All 50 listeners registered')

  // Broadcast message
  const wsA = MockWebSocket.all[0]
  wsA.sendServerMessage({ castle_1: 'running', castle_2: 'idle' })
  assert.strictEqual(notifyCountA, 50, 'All 50 listeners notified from single broadcast')
  console.log('  [PASS] 50 cards share exactly 1 WebSocket and receive broadcasts seamlessly')

  // Test 2: Reference Counting & Grace Period
  console.log('\n--- Suite 2: Ref-Counting & Grace-Period Lifecycle ---')
  for (let i = 0; i < 49; i++) {
    unsubsA[i]()
  }
  assert.strictEqual(multiplexers.get(userA).listeners.size, 1, '1 listener remains')
  assert.strictEqual(wsA.closed, false, 'WebSocket remains open with 1 card mounted')

  // Unmount last card
  unsubsA[49]()
  assert.strictEqual(multiplexers.get(userA).listeners.size, 0, '0 listeners left')
  assert.strictEqual(wsA.closed, false, 'WebSocket still open during grace period')
  assert.ok(multiplexers.get(userA).graceTimer !== null, 'Grace timer started')

  // Fast remount
  await new Promise((r) => setTimeout(r, 30))
  const unsubRemount = getOrCreateMultiplexer(userA).subscribe(() => {})
  assert.strictEqual(multiplexers.get(userA).graceTimer, null, 'Grace timer cancelled on fast remount')
  assert.strictEqual(wsA.closed, false, 'WebSocket never closed on fast remount')

  // Final unmount and wait for grace expiry
  unsubRemount()
  await new Promise((r) => setTimeout(r, 200))
  assert.strictEqual(wsA.closed, true, 'WebSocket closed after grace timer expired')
  assert.strictEqual(multiplexers.has(userA), false, 'User multiplexer deleted from registry')
  console.log('  [PASS] Ref-counting, grace period cancellation, and final cleanup verified')

  // Test 3: Account Switch Teardown
  console.log('\n--- Suite 3: Account Switch / Logout Teardown ---')
  MockWebSocket.all = []
  MockWebSocket.active.clear()

  for (const uid of ['u1', 'u2', 'u3', 'u4']) {
    for (let i = 0; i < 10; i++) {
      getOrCreateMultiplexer(uid).subscribe(() => {})
    }
  }

  assert.strictEqual(multiplexers.size, 4, '4 users active')
  assert.strictEqual(MockWebSocket.active.size, 4, '4 active WebSockets in pool')

  purgeAllUserStatusSockets()
  assert.strictEqual(multiplexers.size, 0, 'All multiplexers cleared from registry')
  assert.strictEqual(MockWebSocket.active.size, 0, 'All WebSockets closed immediately')
  console.log('  [PASS] purgeAllUserStatusSockets tears down all user connections immediately')

  console.log('\n' + '='.repeat(78))
  console.log('>>> ALL NODE.JS MULTIPLEXER STRESS TESTS PASSED SUCCESSFULLY! <<<')
  console.log('='.repeat(78))
}

runTests().catch((err) => {
  console.error('Stress test failed:', err)
  process.exit(1)
})
