// ════════════════════════════════════════════════════════════════════
//  botApi.ts — عميل API للتواصل مع api_server.py (خادم البوت)
// ════════════════════════════════════════════════════════════════════
// يُستخدم بدلاً من (أو بجانب) Firebase لتشغيل/إيقاف البوت مباشرة.
// المحلي:   http://localhost:8000
// VPS:      https://yourdomain.com (عبر متغير البيئة VITE_BOT_API_URL)
// ════════════════════════════════════════════════════════════════════

import { auth } from './firebase'

const API_URL = import.meta.env.VITE_BOT_API_URL ?? 'http://localhost:8000'

export interface BotStartPayload {
  castle_id:     string
  user_id:       string
  email:         string
  password?:     string
  config:        Record<string, unknown>
  loop_interval?: number
}

export interface BotStatusResult {
  castle_id: string
  status:    'running' | 'starting' | 'idle' | 'error'
}

// ── استخراج توكن الأمان من Firebase Authentication ────────────────
export async function getAuthHeader(): Promise<Record<string, string>> {
  try {
    const user = auth.currentUser
    if (user) {
      const token = await user.getIdToken()
      return { Authorization: `Bearer ${token}` }
    }
  } catch (err) {
    console.warn('Failed to retrieve Firebase auth token for API request:', err)
  }
  return {}
}

// ── هل الخادم متاح؟ ───────────────────────────────────────────────
export async function checkApiAvailable(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/health`, { signal: AbortSignal.timeout(3000) })
    if (res.ok) return true
    const fallback = await fetch(`${API_URL}/`, { signal: AbortSignal.timeout(3000) })
    return fallback.ok
  } catch {
    return false
  }
}

// ── تشغيل بوت ─────────────────────────────────────────────────────
export async function startBot(payload: BotStartPayload): Promise<{ status: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${API_URL}/api/bot/start`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تشغيل البوت: ${err}`)
  }
  return res.json()
}

// ── إيقاف بوت لقلعة معينة ─────────────────────────────────────────
export async function stopBot(castleId: string): Promise<{ status: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${API_URL}/api/bot/stop/${castleId}`, {
    method:  'POST',
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل إيقاف البوت: ${err}`)
  }
  return res.json()
}

// ── إيقاف جميع بوتات المستخدم (خاص بالإدارة عند الحظر/انتهاء الاشتراك) ──
export async function stopUserBots(userId: string): Promise<{ status: string; stopped_count: number }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${API_URL}/api/bot/stop-user/${userId}`, {
    method:  'POST',
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل إيقاف بوتات المستخدم: ${err}`)
  }
  return res.json()
}

// ── حالة بوت واحد ─────────────────────────────────────────────────
export async function getBotStatus(castleId: string): Promise<BotStatusResult> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${API_URL}/api/bot/status/${castleId}`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new Error('فشل جلب حالة البوت')
  return res.json()
}

// ── حالة جميع البوتات ─────────────────────────────────────────────
export async function getAllBotStatus(): Promise<Record<string, string>> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${API_URL}/api/bot/status`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new Error('فشل جلب الحالات')
  const data = await res.json()
  return data.bots ?? {}
}

// ── WebSocket URL للـ logs المباشرة ────────────────────────────────
export async function getLogsWsUrl(castleId: string): Promise<string> {
  const wsBase = API_URL.replace(/^http/, 'ws')
  try {
    const user = auth.currentUser
    if (user) {
      const token = await user.getIdToken()
      return `${wsBase}/ws/logs/${castleId}?token=${encodeURIComponent(token)}`
    }
  } catch {}
  return `${wsBase}/ws/logs/${castleId}`
}
