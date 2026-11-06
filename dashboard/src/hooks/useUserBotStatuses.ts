// ════════════════════════════════════════════════════════════════════
//  useUserBotStatuses.ts — اشتراك WebSocket موحد ومجمع لحالات البوت
// ════════════════════════════════════════════════════════════════════
// ينشئ اتصال WebSocket واحد فقط لكل مستخدم (/ws/user-status/{user_id})
// ويبث التحديثات اللحظية لكافة بطاقات القلاع ومكونات الواجهة المشتركة.
// يمنع التكرار (Deduplication) وتسريب الاتصالات (Connection Leaks).
// ════════════════════════════════════════════════════════════════════

import { useEffect, useState, useRef, useCallback } from 'react'
import { getWsBaseUrl } from '../lib/botApi'
import { auth } from '../lib/firebase'

export type RealStatus =
  | 'running'
  | 'starting'
  | 'idle'
  | 'disconnected'
  | 'reconnecting'
  | 'waiting'
  | 'offline'
  | 'deploying'
  | 'error'

type StatusListener = (statuses: Record<string, RealStatus>) => void

class UserStatusMultiplexer {
  private userId: string
  private ws: WebSocket | null = null
  private listeners = new Set<StatusListener>()
  private latestStatuses: Record<string, RealStatus> = {}
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private graceTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 2000
  private isDestroyed = false

  constructor(userId: string) {
    this.userId = userId
  }

  public subscribe(listener: StatusListener): () => void {
    if (this.graceTimer) {
      clearTimeout(this.graceTimer)
      this.graceTimer = null
    }

    this.listeners.add(listener)

    // Send immediate snapshot if available
    if (Object.keys(this.latestStatuses).length > 0) {
      listener(this.latestStatuses)
    }

    // Connect if not already connected
    if (!this.ws || this.ws.readyState === WebSocket.CLOSED || this.ws.readyState === WebSocket.CLOSING) {
      this.connect()
    }

    return () => {
      this.listeners.delete(listener)
      if (this.listeners.size === 0) {
        // Start grace period before closing socket to prevent thrashing during route transitions
        this.graceTimer = setTimeout(() => {
          this.disconnect()
          multiplexers.delete(this.userId)
        }, 3000)
      }
    }
  }

  public getStatus(castleId: string): RealStatus | undefined {
    return this.latestStatuses[castleId]
  }

  public getSnapshot(): Record<string, RealStatus> {
    return { ...this.latestStatuses }
  }

  private connect() {
    if (this.isDestroyed || !this.userId) return

    try {
      const wsBase = getWsBaseUrl()
      this.ws = new WebSocket(`${wsBase}/ws/user-status/${this.userId}`)

      this.ws.onopen = () => {
        this.reconnectDelay = 2000 // Reset backoff delay on successful connection
      }

      this.ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data)
          if (parsed && typeof parsed === 'object') {
            this.latestStatuses = {
              ...this.latestStatuses,
              ...parsed,
            }
            this.notify()
          }
        } catch {
          // ignore non-json messages
        }
      }

      this.ws.onclose = () => {
        if (!this.isDestroyed && this.listeners.size > 0) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = () => {
        if (this.ws) {
          try {
            this.ws.close()
          } catch {
            // ignore
          }
        }
      }
    } catch {
      if (!this.isDestroyed && this.listeners.size > 0) {
        this.scheduleReconnect()
      }
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, this.reconnectDelay)

    // Exponential backoff capped at 10 seconds
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 10000)
  }

  private notify() {
    const snapshot = this.getSnapshot()
    for (const listener of this.listeners) {
      try {
        listener(snapshot)
      } catch {
        // prevent one failing listener from breaking others
      }
    }
  }

  public disconnect() {
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
      } catch {
        // ignore
      }
      this.ws = null
    }
  }
}

// Global registry of multiplexers keyed by userId
const multiplexers = new Map<string, UserStatusMultiplexer>()

export function getOrCreateMultiplexer(userId: string): UserStatusMultiplexer {
  let m = multiplexers.get(userId)
  if (!m) {
    m = new UserStatusMultiplexer(userId)
    multiplexers.set(userId, m)
  }
  return m
}

/**
 * Disconnects and purges all active multiplexed WebSockets.
 * Call during logout or tenant change.
 */
export function purgeAllUserStatusSockets() {
  for (const [, multiplexer] of multiplexers) {
    multiplexer.disconnect()
  }
  multiplexers.clear()
}

/**
 * Single multiplexed WebSocket hook for all user castle statuses.
 * Replaces redundant per-castle WebSocket connections.
 */
export function useUserBotStatuses(userId?: string, enabled: boolean = true) {
  const activeUserId = userId || auth.currentUser?.uid || ''
  const [statuses, setStatuses] = useState<Record<string, RealStatus>>(() => {
    if (!activeUserId) return {}
    return multiplexers.get(activeUserId)?.getSnapshot() || {}
  })

  useEffect(() => {
    if (!enabled || !activeUserId) {
      return
    }

    const multiplexer = getOrCreateMultiplexer(activeUserId)
    const unsubscribe = multiplexer.subscribe((updated) => {
      setStatuses(updated)
    })

    return () => {
      unsubscribe()
    }
  }, [activeUserId, enabled])

  return { statuses }
}

/**
 * Hook for a single castle card to read live status from the multiplexed user WebSocket
 * without creating an individual WebSocket connection.
 */
export function useMultiplexedBotStatus(
  castleId: string,
  userId?: string,
  fallbackStatus: RealStatus = 'offline',
  enabled: boolean = true
): { status: RealStatus } {
  const activeUserId = userId || auth.currentUser?.uid || ''
  const [status, setStatus] = useState<RealStatus>(() => {
    if (!activeUserId || !castleId) return fallbackStatus
    return multiplexers.get(activeUserId)?.getStatus(castleId) || fallbackStatus
  })

  useEffect(() => {
    if (!enabled || !activeUserId || !castleId) {
      return
    }

    const multiplexer = getOrCreateMultiplexer(activeUserId)
    const current = multiplexer.getStatus(castleId)
    if (current && current !== status) {
      setStatus(current)
    }

    const unsubscribe = multiplexer.subscribe((allStatuses) => {
      const s = allStatuses[castleId]
      if (s) {
        setStatus(s)
      }
    })

    return () => {
      unsubscribe()
    }
  }, [activeUserId, castleId, enabled])

  return { status }
}
