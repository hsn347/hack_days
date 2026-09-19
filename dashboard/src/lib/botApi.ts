// ════════════════════════════════════════════════════════════════════
//  botApi.ts — عميل API للتواصل مع api_server.py (خادم البوت و SQLite)
// ════════════════════════════════════════════════════════════════════
// يعتمد كلياً على SQLite عبر REST API وخادم FastAPI، بدون Firestore.
// المحلي:   http://localhost:8000
// VPS:      https://ibraabot.online (عبر متغير البيئة VITE_BOT_API_URL)
// ════════════════════════════════════════════════════════════════════

import { auth } from './firebase'
import type { Castle, CastleConfig, User } from '../types'

export function getApiBaseUrl(): string {
  // 1. إذا كان الكود يعمل في المتصفح على نطاق عام
  if (typeof window !== 'undefined' && window.location?.origin) {
    const origin = window.location.origin
    if (!origin.includes('localhost') && !origin.includes('127.0.0.1')) {
      return origin
    }
  }

  // 2. متغير البيئة إذا وُجد ولم يكن localhost
  const envUrl = (import.meta.env.VITE_BOT_API_URL as string | undefined)?.trim()
  if (envUrl && !envUrl.includes('localhost') && !envUrl.includes('127.0.0.1')) {
    return envUrl.replace(/\/+$/, '')
  }

  // 3. الوضع الافتراضي للتطوير المحلي
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin
  }
  return 'http://localhost:8000'
}

export function getWsBaseUrl(): string {
  const base = getApiBaseUrl()
  if (base.startsWith('https://')) {
    return base.replace(/^https:\/\//, 'wss://')
  }
  return base.replace(/^http:\/\//, 'ws://')
}

export interface BotStartPayload {
  castle_id:     string
  user_id:       string
  email:         string
  password?:     string
  config?:       Record<string, unknown>
  loop_interval?: number
}

export interface BotStatusResult {
  castle_id: string
  status:    'running' | 'starting' | 'idle' | 'error' | 'disconnected' | 'reconnecting' | 'waiting'
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
    const api = getApiBaseUrl()
    const res = await fetch(`${api}/api/health`, { signal: AbortSignal.timeout(3000) })
    if (res.ok) return true
    const fallback = await fetch(`${api}/`, { signal: AbortSignal.timeout(3000) })
    return fallback.ok
  } catch {
    return false
  }
}

// ══════════════════════════════════════════════════════════════════
// 👤 دوال إدارة المستخدمين (User REST APIs)
// ══════════════════════════════════════════════════════════════════

export async function getUserProfile(): Promise<User | null> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/user/profile`, {
    headers: authHeaders,
  })
  if (!res.ok) return null
  const data = await res.json()
  return data.user ? formatUserFromApi(data.user) : null
}

export async function registerUser(payload: {
  uid:       string
  email:     string
  username?: string
  phone?:    string
}): Promise<{ status: string; user: User }> {
  const res = await fetch(`${getApiBaseUrl()}/api/user/register`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تسجيل المستخدم: ${err}`)
  }
  const data = await res.json()
  return { status: data.status, user: formatUserFromApi(data.user) }
}

export async function updateUserProfileApi(payload: {
  username?: string
  phone?:    string
}): Promise<{ status: string; user: User }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/user/profile`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تحديث الملف الشخصي: ${err}`)
  }
  const data = await res.json()
  return { status: data.status, user: formatUserFromApi(data.user) }
}

export async function getUserSubscription(): Promise<Record<string, unknown>> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/user/subscription`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new Error('فشل جلب تفاصيل الاشتراك')
  return res.json()
}

// ══════════════════════════════════════════════════════════════════
// 🏰 دوال إدارة القلاع (Castles REST APIs)
// ══════════════════════════════════════════════════════════════════

export async function fetchCastles(userId?: string): Promise<Castle[]> {
  const authHeaders = await getAuthHeader()
  const url = userId && userId.trim()
    ? `${getApiBaseUrl()}/api/castles?user_id=${encodeURIComponent(userId.trim())}`
    : `${getApiBaseUrl()}/api/castles`
  const res = await fetch(url, {
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل جلب القلاع: ${err}`)
  }
  const data = await res.json()
  return (data.castles || []).map((c: any) => formatCastleFromApi(c))
}

export async function fetchCastle(castleId: string): Promise<Castle> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}`, {
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل جلب بيانات القلعة: ${err}`)
  }
  const data = await res.json()
  return formatCastleFromApi(data.castle)
}

export async function createCastle(payload: {
  castle_id?:   string
  email:         string
  password?:     string
  castle_name?:  string
  config?:       Record<string, unknown>
}): Promise<{ status: string; castle: Castle }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    let detail = err
    try {
      const parsed = JSON.parse(err)
      if (parsed.detail) detail = parsed.detail
    } catch { /* empty */ }
    throw new Error(detail)
  }
  const data = await res.json()
  return { status: data.status, castle: formatCastleFromApi(data.castle) }
}

export async function updateCastle(castleId: string, payload: {
  castle_name?: string
  config?:      Record<string, unknown>
}): Promise<{ status: string; castle: Castle }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    let detail = err
    try {
      const parsed = JSON.parse(err)
      if (parsed.detail) detail = parsed.detail
    } catch { /* empty */ }
    throw new Error(detail)
  }
  const data = await res.json()
  return { status: data.status, castle: formatCastleFromApi(data.castle) }
}

export async function updateCastleCredentials(castleId: string, payload: {
  email:    string
  password?: string
}): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}/credentials`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    let detail = err
    try {
      const parsed = JSON.parse(err)
      if (parsed.detail) detail = parsed.detail
    } catch { /* empty */ }
    throw new Error(detail)
  }
  return res.json()
}

export async function toggleCastleActive(castleId: string, isActive: boolean): Promise<{ status: string; is_active: boolean }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}/toggle-active`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ is_active: isActive }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تعديل حالة القلعة: ${err}`)
  }
  return res.json()
}

export async function deleteCastle(castleId: string): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}`, {
    method:  'DELETE',
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل حذف القلعة: ${err}`)
  }
  return res.json()
}

export async function fetchCastleDataLive(email: string, userId?: string, castleId?: string): Promise<Record<string, unknown>> {
  const authHeaders = await getAuthHeader()
  const query = new URLSearchParams()
  if (userId) query.set('user_id', userId)
  if (castleId) query.set('castle_id', castleId)

  const res = await fetch(`${getApiBaseUrl()}/api/castle-data/${encodeURIComponent(email)}?${query.toString()}`, {
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل استعلام بيانات القلعة الحية: ${err}`)
  }
  return res.json()
}

// ══════════════════════════════════════════════════════════════════
// 👑 دوال لوحة الإدارة (Admin REST APIs)
// ══════════════════════════════════════════════════════════════════

export async function getAdminStats(): Promise<{ totalUsers: number; activeSubscriptions: number; totalCastles: number; activeBots?: number }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/stats`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new Error('فشل جلب الإحصائيات')
  return res.json()
}

export async function getAdminUsers(): Promise<User[]> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/users`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new Error('فشل جلب المستخدمين')
  const data = await res.json()
  return (data.users || []).map((u: any) => formatUserFromApi(u))
}

export async function updateAdminSubscription(uid: string, payload: {
  plan_id:             string
  plan_name:           string
  subscription_status?: string
  expires_at:          string
  max_castles_allowed: number
}): Promise<{ status: string; user: User }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/user/${uid}/subscription`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تعديل الاشتراك: ${err}`)
  }
  const data = await res.json()
  return { status: data.status, user: formatUserFromApi(data.user) }
}

export async function banAdminUser(uid: string, payload: {
  is_banned: boolean
  reason?:   string
}): Promise<{ status: string; user: User }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/user/${uid}/ban`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل حظر/إلغاء حظر المستخدم: ${err}`)
  }
  const data = await res.json()
  return { status: data.status, user: formatUserFromApi(data.user) }
}

export async function deleteAdminUser(uid: string): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/user/${uid}`, {
    method:  'DELETE',
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل حذف المستخدم: ${err}`)
  }
  return res.json()
}

export async function approveAdminUser(
  uid: string,
  days = 3,
  maxCastles = 10
): Promise<{ status: string; message: string; user: User }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/user/${uid}/approve`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ days, max_castles: maxCastles }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تفعيل باقة المستخدم: ${err}`)
  }
  const data = await res.json()
  return { status: data.status, message: data.message, user: formatUserFromApi(data.user) }
}

export async function approveAllPendingAdminUsers(
  days = 3,
  maxCastles = 10
): Promise<{ status: string; message: string; approved_count: number }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/users/approve-all`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ days, max_castles: maxCastles }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تفعيل باقة المستخدمين: ${err}`)
  }
  return res.json()
}

export async function approveCastleAdmin(castleId: string): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/castle/${castleId}/approve`, {
    method:  'POST',
    headers: authHeaders,
  })
  if (!res.ok) throw new Error('فشل قبول القلعة')
  return res.json()
}

export async function rejectCastleAdmin(castleId: string, reason?: string): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/castle/${castleId}/reject`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ reason }),
  })
  if (!res.ok) throw new Error('فشل رفض القلعة')
  return res.json()
}

// ══════════════════════════════════════════════════════════════════
// 🤖 التحكم في البوت (Bot Execution Controls)
// ══════════════════════════════════════════════════════════════════

export async function startBot(payload: BotStartPayload): Promise<{ status: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/start`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err.includes('detail') ? JSON.parse(err).detail : err)
  }
  return res.json()
}

export async function stopBot(castleId: string): Promise<{ status: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/stop/${castleId}`, {
    method:  'POST',
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل إيقاف البوت: ${err}`)
  }
  return res.json()
}

export async function stopUserBots(userId: string): Promise<{ status: string; stopped_count: number }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/stop-user/${userId}`, {
    method:  'POST',
    headers: authHeaders,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل إيقاف بوتات المستخدم: ${err}`)
  }
  return res.json()
}

export async function getBotStatus(castleId: string): Promise<BotStatusResult> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/status/${castleId}`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new Error('فشل جلب حالة البوت')
  return res.json()
}

export async function getAllBotStatus(): Promise<Record<string, string>> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/status`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new Error('فشل جلب الحالات')
  const data = await res.json()
  return data.bots ?? {}
}

export async function getLogsWsUrl(castleId: string): Promise<string> {
  const wsBase = getWsBaseUrl()
  try {
    const user = auth.currentUser
    if (user) {
      const token = await user.getIdToken()
      return `${wsBase}/ws/logs/${castleId}?token=${encodeURIComponent(token)}`
    }
  } catch {}
  return `${wsBase}/ws/logs/${castleId}`
}

// ══════════════════════════════════════════════════════════════════
// 🔄 Helpers لتحويل هياكل البيانات القادمة من SQLite لتطابق الواجهة
// ══════════════════════════════════════════════════════════════════

export function formatCastleFromApi(raw: any): Castle {
  if (!raw) return {} as Castle

  const cfg = typeof raw.config === 'string' ? JSON.parse(raw.config || '{}') : (raw.config || {})

  return {
    id:          raw.castle_id || raw.id,
    castle_id:   raw.castle_id || raw.id,
    email:       raw.email || '',
    user_id:     raw.user_id,
    is_active:   raw.is_active !== undefined ? Boolean(raw.is_active) : true,
    created_at:  raw.created_at || new Date().toISOString(),
    castle_info: {
      lord_name:    raw.lord_name || (raw.email ? raw.email.split('@')[0] : 'قلعة'),
      castle_name:  raw.castle_name || (raw.email ? raw.email.split('@')[0] : 'قلعة'),
      server_id:    raw.server_id ?? 1,
      castle_level: raw.castle_level ?? 1,
      walls_level:  raw.walls_level ?? 0,
      lord_power:   raw.lord_power ?? 0,
      vip_level:    raw.vip_level ?? 0,
      alliance_name:raw.alliance_name || '',
      coordinates:  { x: raw.coord_x ?? 0, y: raw.coord_y ?? 0 },
    },
    resources: {
      food:         raw.food ?? 0,
      wood:         raw.wood ?? 0,
      iron:         raw.iron ?? 0,
      diamond:      raw.diamond ?? 0,
      gold:         raw.gold ?? 0,
      stamina:      raw.stamina ?? 100,
      last_updated: raw.last_updated || new Date().toISOString(),
    },
    bot_status: {
      state:            raw.state || 'idle',
      conn_state:       raw.conn_state || raw.state || 'idle',
      conn_message:     raw.conn_message || '',
      conn_updated:     raw.last_updated || new Date().toISOString(),
      last_run_time:    raw.last_run_time || null,
      next_run_time:    raw.next_run_time || null,
      last_run_message: raw.last_run_message || (raw.state === 'running' ? 'البوت يعمل الآن...' : 'جاهز للتشغيل'),
      active_marches:   0,
      max_marches:      2,
      last_error:       null,
    },
    config: cfg,
  } as Castle
}

export function formatUserFromApi(raw: any): User {
  if (!raw) return {} as User

  const expRaw = raw.subscription_expires_at || raw.subscription?.expires_at || null
  const expDate = expRaw ? new Date(expRaw) : null
  const now = new Date()
  const daysRemaining = (expDate && !isNaN(expDate.getTime()))
    ? Math.max(0, Math.ceil((expDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)))
    : (raw.subscription?.days_remaining ?? 0)

  const status = (raw.subscription_status || raw.subscription?.status || 'pending_approval') as 'active' | 'expired' | 'suspended' | 'pending_approval'
  const isPending = status === 'pending_approval'

  return {
    uid:        raw.uid,
    email:      raw.email,
    username:   raw.username || (raw.email ? raw.email.split('@')[0] : ''),
    phone:      raw.phone || '',
    role:       raw.role || 'user',
    is_banned:  Boolean(raw.is_banned),
    banned_reason: raw.banned_reason || '',
    created_at: raw.created_at || new Date().toISOString(),
    subscription: {
      plan_id:               raw.plan_id || raw.subscription?.plan_id || (isPending ? 'pending_trial' : 'free'),
      plan_name:             raw.plan_name || raw.subscription?.plan_name || (isPending ? 'بانتظار موافقة الإدارة' : 'مجاني'),
      status:                status,
      started_at:            raw.subscription_started_at || raw.subscription?.started_at || '',
      expires_at:            expRaw || '',
      days_remaining:        isPending ? 0 : daysRemaining,
      max_castles_allowed:   raw.max_castles_allowed ?? raw.subscription?.max_castles_allowed ?? (isPending ? 0 : 1),
      current_castles_count: raw.current_castles_count ?? raw.subscription?.current_castles_count ?? 0,
      pending_castles_count: raw.pending_castles_count ?? raw.subscription?.pending_castles_count ?? 0,
      total_castles_count:   raw.total_castles_count ?? raw.subscription?.total_castles_count ?? (raw.current_castles_count ?? 0),
    },
  } as User
}
