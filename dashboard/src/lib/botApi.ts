// ════════════════════════════════════════════════════════════════════
//  botApi.ts — عميل API للتواصل مع api_server.py (خادم البوت و SQLite)
// ════════════════════════════════════════════════════════════════════
// يعتمد كلياً على SQLite عبر REST API وخادم FastAPI، بدون Firestore.
// المحلي:   http://localhost:8000
// VPS:      https://ibraabot.online (عبر متغير البيئة VITE_BOT_API_URL)
// ════════════════════════════════════════════════════════════════════

import { auth } from './firebase'
import type { Castle, CastleConfig, User } from '../types'
import i18n from './i18n'
import { localizeApiError } from './localize'

export interface RequestOptions {
  signal?: AbortSignal
}

export function isAbortError(err: unknown): boolean {
  if (!err) return false
  if (typeof DOMException !== 'undefined' && err instanceof DOMException && err.name === 'AbortError') {
    return true
  }
  const e = err as { name?: string; message?: string }
  return e?.name === 'AbortError' || e?.message === 'The user aborted a request.' || e?.message?.includes('aborted') === true
}

export function parseAndLocalizeApiError(errText: string): string {
  if (errText && (errText.includes('AbortError') || errText.includes('aborted'))) {
    return ''
  }
  let detail = errText
  try {
    const parsed = JSON.parse(errText)
    if (parsed.detail) detail = parsed.detail
  } catch { /* empty */ }
  return localizeApiError(detail, i18n.t)
}


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
  const headers: Record<string, string> = {}
  try {
    const user = auth.currentUser
    if (user) {
      const token = await user.getIdToken()
      headers['Authorization'] = `Bearer ${token}`
    }
  } catch (err) {
    console.warn('Failed to retrieve Firebase auth token for API request:', err)
  }
  if (typeof window !== 'undefined' && window.location?.hostname) {
    headers['X-Tenant-Domain'] = window.location.hostname
  }
  return headers
}

// ── هل الخادم متاح؟ ───────────────────────────────────────────────
export async function checkApiAvailable(options?: RequestOptions): Promise<boolean> {
  try {
    const api = getApiBaseUrl()
    const signal = options?.signal || AbortSignal.timeout(3000)
    const res = await fetch(`${api}/api/health`, { signal })
    if (res.ok) return true
    const fallback = await fetch(`${api}/`, { signal })
    return fallback.ok
  } catch {
    return false
  }
}

// ══════════════════════════════════════════════════════════════════
// 👤 دوال إدارة المستخدمين (User REST APIs)
// ══════════════════════════════════════════════════════════════════

export async function getUserProfile(options?: RequestOptions): Promise<User | null> {
  const authHeaders = await getAuthHeader()
  if (!authHeaders.Authorization) return null
  const res = await fetch(`${getApiBaseUrl()}/api/user/profile`, {
    headers: authHeaders,
    signal: options?.signal,
  })
  if (res.status === 403) {
    const data = await res.json().catch(() => ({}))
    const msg = data.detail || 'هذا الحساب غير مسجل في هذا النظام'
    const err = new Error(msg)
    ;(err as any).status = 403
    ;(err as any).code = 'auth/tenant-mismatch'
    throw err
  }
  if (!res.ok) return null
  const data = await res.json()
  return data.user ? formatUserFromApi(data.user) : null
}

export async function registerUser(payload: {
  uid:            string
  email:          string
  username?:      string
  phone?:         string
  tenant_domain?: string
}, options?: RequestOptions): Promise<{ status: string; user: User }> {
  const res = await fetch(`${getApiBaseUrl()}/api/user/register`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
    signal:  options?.signal,
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
}, options?: RequestOptions): Promise<{ status: string; user: User }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/user/profile`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تحديث الملف الشخصي: ${err}`)
  }
  const data = await res.json()
  return { status: data.status, user: formatUserFromApi(data.user) }
}

export async function getUserSubscription(options?: RequestOptions): Promise<Record<string, unknown>> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/user/subscription`, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل جلب تفاصيل الاشتراك')
  return res.json()
}

// ══════════════════════════════════════════════════════════════════
// 🏰 دوال إدارة القلاع (Castles REST APIs)
// ══════════════════════════════════════════════════════════════════

export async function fetchCastles(userId?: string, options?: RequestOptions): Promise<Castle[]> {
  const authHeaders = await getAuthHeader()
  const url = userId && userId.trim()
    ? `${getApiBaseUrl()}/api/castles?user_id=${encodeURIComponent(userId.trim())}`
    : `${getApiBaseUrl()}/api/castles`
  const res = await fetch(url, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل جلب القلاع: ${err}`)
  }
  const data = await res.json()
  return (data.castles || []).map((c: any) => formatCastleFromApi(c))
}

export async function fetchCastle(castleId: string, options?: RequestOptions): Promise<Castle> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}`, {
    headers: authHeaders,
    signal:  options?.signal,
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
}, options?: RequestOptions): Promise<{ status: string; castle: Castle }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  const data = await res.json()
  return { status: data.status, castle: formatCastleFromApi(data.castle) }
}

export async function updateCastle(castleId: string, payload: {
  castle_name?:   string
  config?:        Record<string, unknown>
  version?:       number
  loop_interval?: number
}, options?: RequestOptions): Promise<{ status: string; castle: Castle }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
    signal:  options?.signal,
  })
  if (!res.ok) {
    if (res.status === 409) {
      const errJson = await res.json().catch(() => ({}))
      const conflictErr = new Error(errJson.detail || 'تعارض في حفظ الإعدادات: تم تعديل البيانات بالتزامن')
      ;(conflictErr as any).status = 409
      ;(conflictErr as any).isConflict = true
      throw conflictErr
    }
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  const data = await res.json()
  return { status: data.status, castle: formatCastleFromApi(data.castle) }
}

export async function updateCastlesLoopIntervals(intervals: Record<string, number>, options?: RequestOptions): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/loop-intervals`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ intervals }),
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  return res.json()
}

export async function updateCastleCredentials(castleId: string, payload: {
  email:    string
  password?: string
}, options?: RequestOptions): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}/credentials`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  return res.json()
}

export async function toggleCastleActive(castleId: string, isActive: boolean, options?: RequestOptions): Promise<{ status: string; is_active: boolean }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}/toggle-active`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ is_active: isActive }),
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  return res.json()
}

export async function deleteCastle(castleId: string, options?: RequestOptions): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/castles/${castleId}`, {
    method:  'DELETE',
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  return res.json()
}

export async function fetchCastleDataLive(email: string, userId?: string, castleId?: string, options?: RequestOptions): Promise<Record<string, unknown>> {
  const authHeaders = await getAuthHeader()
  const query = new URLSearchParams()
  if (userId) query.set('user_id', userId)
  if (castleId) query.set('castle_id', castleId)

  const res = await fetch(`${getApiBaseUrl()}/api/castle-data/${encodeURIComponent(email)}?${query.toString()}`, {
    headers: authHeaders,
    signal:  options?.signal,
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

export async function getAdminStats(options?: RequestOptions): Promise<{ totalUsers: number; activeSubscriptions: number; totalCastles: number; activeBots?: number }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/stats`, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل جلب الإحصائيات')
  return res.json()
}

export async function getAdminUsers(options?: RequestOptions): Promise<User[]> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/users`, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل جلب المستخدمين')
  const data = await res.json()
  return (data.users || []).map((u: any) => formatUserFromApi(u))
}

export interface MerchantStats {
  id: string
  brand_name: string
  domains: string[]
  admin_email: string
  primary_color: string
  tagline?: string
  total_users: number
  total_castles: number
  running_castles: number
}

export async function getMerchantsOverview(options?: RequestOptions): Promise<{ status: string; merchants: MerchantStats[] }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/merchants/overview`, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل جلب إحصائيات التجار')
  return res.json()
}

export async function updateAdminSubscription(uid: string, payload: {
  plan_id:             string
  plan_name:           string
  subscription_status?: string
  expires_at:          string
  max_castles_allowed: number
}, options?: RequestOptions): Promise<{ status: string; user: User }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/user/${uid}/subscription`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
    signal:  options?.signal,
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
}, options?: RequestOptions): Promise<{ status: string; user: User }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/user/${uid}/ban`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل حظر/إلغاء حظر المستخدم: ${err}`)
  }
  const data = await res.json()
  return { status: data.status, user: formatUserFromApi(data.user) }
}

export async function deleteAdminUser(uid: string, options?: RequestOptions): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/user/${uid}`, {
    method:  'DELETE',
    headers: authHeaders,
    signal:  options?.signal,
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
  maxCastles = 10,
  options?: RequestOptions
): Promise<{ status: string; message: string; user: User }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/user/${uid}/approve`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ days, max_castles: maxCastles }),
    signal:  options?.signal,
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
  maxCastles = 10,
  options?: RequestOptions
): Promise<{ status: string; message: string; approved_count: number }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/users/approve-all`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ days, max_castles: maxCastles }),
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`فشل تفعيل باقة المستخدمين: ${err}`)
  }
  return res.json()
}

export async function approveCastleAdmin(castleId: string, options?: RequestOptions): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/castle/${castleId}/approve`, {
    method:  'POST',
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل قبول القلعة')
  return res.json()
}

export async function rejectCastleAdmin(castleId: string, reason?: string, options?: RequestOptions): Promise<{ status: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/castle/${castleId}/reject`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify({ reason }),
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل رفض القلعة')
  return res.json()
}

// ══════════════════════════════════════════════════════════════════
// 🤖 التحكم في البوت (Bot Execution Controls)
// ══════════════════════════════════════════════════════════════════

export async function startBot(payload: BotStartPayload, options?: RequestOptions): Promise<{ status: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/start`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body:    JSON.stringify(payload),
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  return res.json()
}

export async function stopBot(castleId: string, options?: RequestOptions): Promise<{ status: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/stop/${castleId}`, {
    method:  'POST',
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  return res.json()
}

export async function stopUserBots(userId: string, options?: RequestOptions): Promise<{ status: string; stopped_count: number }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/stop-user/${userId}`, {
    method:  'POST',
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(parseAndLocalizeApiError(err))
  }
  return res.json()
}

export async function getBotStatus(castleId: string, options?: RequestOptions): Promise<BotStatusResult> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/status/${castleId}`, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل جلب حالة البوت')
  return res.json()
}

export async function getAllBotStatus(options?: RequestOptions): Promise<Record<string, string>> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/bot/status`, {
    headers: authHeaders,
    signal:  options?.signal,
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
      coordinates:  { x: raw.coord_x ?? (raw.coordinates?.x ?? 0), y: raw.coord_y ?? (raw.coordinates?.y ?? 0) },
      avatar:       raw.avatar || (raw.castle_info?.avatar || ''),
      image_id:     raw.image_id ?? (raw.castle_info?.image_id ?? 0),
    },
    resources: {
      food:                raw.food ?? 0,
      wood:                raw.wood ?? 0,
      iron:                raw.iron ?? 0,
      diamond:             raw.diamond ?? 0,
      gold:                raw.gold ?? 0,
      stamina:             raw.stamina ?? 100,
      unprotected_food:    raw.unprotected_food ?? (raw.resources?.unprotected_food ?? 0),
      unprotected_wood:    raw.unprotected_wood ?? (raw.resources?.unprotected_wood ?? 0),
      unprotected_iron:    raw.unprotected_iron ?? (raw.resources?.unprotected_iron ?? 0),
      unprotected_diamond: raw.unprotected_diamond ?? (raw.resources?.unprotected_diamond ?? 0),
      safe_food:           raw.safe_food ?? (raw.resources?.safe_food ?? 0),
      safe_wood:           raw.safe_wood ?? (raw.resources?.safe_wood ?? 0),
      safe_iron:           raw.safe_iron ?? (raw.resources?.safe_iron ?? 0),
      safe_diamond:        raw.safe_diamond ?? (raw.resources?.safe_diamond ?? 0),
      last_updated:        raw.last_updated || new Date().toISOString(),
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
      last_error:       (raw.state === 'error' || raw.conn_state === 'error') ? (raw.conn_message || 'خطأ في المصادقة أو الاتصال') : (raw.last_error || null),
    },
    version: raw.version ?? 1,
    loop_interval: raw.loop_interval ? Number(raw.loop_interval) : 40,
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
    tenant_domain: raw.tenant_domain || '',
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

// ══════════════════════════════════════════════════════════════════
// ⚡ العمليات الحية (Live Runtime Threads API)
// ══════════════════════════════════════════════════════════════════

export interface LiveProcessInfo {
  castle_id: string
  email: string
  user_id: string
  user_email?: string
  thread_id: number | null
  thread_name: string
  thread_alive: boolean
  state: string
  live_category: 'running' | 'waiting_next_cycle' | 'other_device_login' | 'reconnecting' | 'waiting_relogin' | 'starting' | 'waiting' | 'other_login' | 'stalled' | string
  category_label: string
  current_step?: string
  status_message: string
  iteration: number
  loop_interval_minutes: number
  next_run_time: string | null
  reconnect_attempt: number
  max_reconnect_attempts: number
  last_kick_reason: string
  uptime_seconds: number
  step_duration_seconds?: number
  is_connection_alive: boolean
  is_stopped: boolean
  is_stalled?: boolean
  start_time: number
  proxy_ip?: string
  real_ip?: string
  real_ip_type?: 'socks5' | 'direct' | string
  socket_peer?: string
  is_proxied?: boolean
  is_live_socket?: boolean
}


export interface LiveProcessesResponse {
  status: string
  source: string
  timestamp: string
  total_active: number
  total_count: number
  page: number
  page_size: number
  total_pages: number
  has_more: boolean
  summary: {
    total_active: number
    running: number
    waiting_next_cycle: number
    other_device_login: number
    reconnecting: number
    waiting_relogin: number
    starting: number
    stalled?: number
    stalled_count?: number
    waiting?: number
    other_login?: number
    Running?: number
    'Waiting for Next Cycle'?: number
    'Other Device Login'?: number
    Reconnecting?: number
    'Waiting for Re-login'?: number
    Starting?: number
  }
  processes: LiveProcessInfo[]
  stalled_processes?: LiveProcessInfo[]
}

export interface LiveProcessesQueryParams extends RequestOptions {
  page?: number
  page_size?: number
  search?: string
  status?: string
}

export async function getAdminLiveProcesses(
  params?: LiveProcessesQueryParams,
  options?: RequestOptions
): Promise<LiveProcessesResponse> {
  const authHeaders = await getAuthHeader()
  const q = new URLSearchParams()
  if (params?.page) q.set('page', String(params.page))
  if (params?.page_size) q.set('page_size', String(params.page_size))
  if (params?.search && params.search.trim()) q.set('search', params.search.trim())
  if (params?.status && params.status !== 'all') q.set('status', params.status.trim())

  const effectiveSignal = params?.signal || options?.signal
  const qs = q.toString() ? `?${q.toString()}` : ''
  const res = await fetch(`${getApiBaseUrl()}/api/admin/live-processes${qs}`, {
    headers: authHeaders,
    signal:  effectiveSignal,
  })
  if (!res.ok) throw new Error('فشل جلب العمليات الحية من السيرفر')
  return res.json()
}

// ─── Proxies & Network Mode Management API ────────────────────────────────
export interface ProxyCardInfo {
  ip: string
  port: number
  country: string
  assigned_castles: string[]
  assigned_users: string[]
  full_url: string
}

export interface ProxiesStatusResponse {
  enabled: boolean
  network_mode?: 'socks5' | 'direct'
  server_ip?: string
  total_proxies: number
  total_bound_castles: number
  total_bound_users: number
  proxies_list: ProxyCardInfo[]
}

export async function getAdminProxies(options?: RequestOptions): Promise<ProxiesStatusResponse> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/proxies`, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل جلب بيانات البروكسيات من السيرفر')
  return res.json()
}

export async function testAdminProxy(proxyUrl: string, options?: RequestOptions): Promise<{ ok: boolean; ping?: number; msg: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/proxies/test`, {
    method: 'POST',
    headers: { ...authHeaders, 'Content-Type': 'application/json' },
    body: JSON.stringify({ proxy_url: proxyUrl }),
    signal: options?.signal,
  })
  if (!res.ok) throw new Error('فشل اختبار البروكسي')
  return res.json()
}

export interface NetworkModeResponse {
  status: string
  network_mode: 'socks5' | 'direct'
  server_ip?: string
  enabled: boolean
  total_proxies: number
  total_bound_castles: number
  total_bound_users: number
}

export async function getAdminNetworkMode(options?: RequestOptions): Promise<NetworkModeResponse> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/network-mode`, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) throw new Error('فشل جلب نمط شبكة الاتصال')
  return res.json()
}

export async function toggleAdminNetworkMode(
  mode: 'socks5' | 'direct',
  options?: RequestOptions
): Promise<{ status: string; network_mode: string; message: string }> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/network-mode/toggle`, {
    method: 'POST',
    headers: { ...authHeaders, 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
    signal: options?.signal,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'فشل تغيير نمط الشبكة')
  }
  return res.json()
}

// ─── Super Admin: Users with full Castles List ────────────────
export interface AdminUserWithCastles {
  uid: string
  email: string
  display_name: string
  role: string
  is_banned: boolean
  created_at: string
  tenant_domain: string
  subscription: {
    plan_id: string
    plan_name: string
    status: string
    expires_at: string
    max_castles_allowed: number
  }
  castles: Castle[]
  castles_count: number
  running_count: number
}

export interface CastlePreview {
  id: string
  email: string
}

export interface AdminUserSummary {
  uid: string
  email: string
  display_name: string
  role: string
  is_banned: boolean
  created_at: string
  tenant_domain: string
  subscription: {
    plan_id: string
    plan_name: string
    status: string
    expires_at: string
    max_castles_allowed: number
  }
  castle_count: number
  castles_count: number
  active_count: number
  running_count: number
  pending_count: number
  castle_previews?: CastlePreview[]
}

export interface AdminUsersCastlesSummaryStats {
  total_users: number
  total_castles: number
  total_running: number
}

export interface AdminUsersCastlesPaginatedResponse {
  status: string
  items: AdminUserSummary[]
  users: AdminUserSummary[]
  total: number
  total_count: number
  page: number
  page_size: number
  total_pages: number
  has_more: boolean
  summary_stats?: AdminUsersCastlesSummaryStats
}

export interface AdminUsersCastlesQueryParams {
  page?: number
  pageSize?: number
  search?: string
  filterStatus?: string
}

export async function fetchAdminUsersCastlesSummary(
  paramsOrOptions?: AdminUsersCastlesQueryParams | RequestOptions,
  maybeOptions?: RequestOptions
): Promise<AdminUsersCastlesPaginatedResponse> {
  let params: AdminUsersCastlesQueryParams | undefined
  let options: RequestOptions | undefined

  if (
    paramsOrOptions &&
    'signal' in paramsOrOptions &&
    !('page' in paramsOrOptions) &&
    !('pageSize' in paramsOrOptions) &&
    !('search' in paramsOrOptions)
  ) {
    options = paramsOrOptions as RequestOptions
  } else {
    params = paramsOrOptions as AdminUsersCastlesQueryParams | undefined
    options = maybeOptions
  }

  const authHeaders = await getAuthHeader()
  const searchParams = new URLSearchParams()
  if (params?.page !== undefined) searchParams.set('page', String(params.page))
  if (params?.pageSize !== undefined) searchParams.set('page_size', String(params.pageSize))
  if (params?.search) searchParams.set('search', params.search)
  if (params?.filterStatus && params.filterStatus !== 'all') {
    searchParams.set('filter_status', params.filterStatus)
  }

  const queryStr = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const res = await fetch(`${getApiBaseUrl()}/api/admin/users-castles/summary${queryStr}`, {
    headers: authHeaders,
    signal: options?.signal,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'فشل جلب ملخص المستخدمين')
  }
  const data = await res.json()
  const rawUsers = data?.items || data?.users || (Array.isArray(data) ? data : [])
  const users: AdminUserSummary[] = rawUsers.map((u: any) => ({
    ...u,
    castles_count: u.castles_count ?? u.castle_count ?? 0,
    castle_count: u.castle_count ?? u.castles_count ?? 0,
    running_count: u.running_count ?? u.active_count ?? 0,
    active_count: u.active_count ?? u.running_count ?? 0,
    pending_count: u.pending_count ?? 0,
  }))

  const total = data?.total ?? data?.total_count ?? users.length
  const page = data?.page ?? params?.page ?? 1
  const pageSize = data?.page_size ?? params?.pageSize ?? (users.length || 25)
  const totalPages = data?.total_pages ?? Math.max(1, Math.ceil(total / pageSize))
  const hasMore = data?.has_more ?? (page < totalPages)

  return {
    status: data?.status || 'success',
    items: users,
    users,
    total,
    total_count: total,
    page,
    page_size: pageSize,
    total_pages: totalPages,
    has_more: hasMore,
    summary_stats: data?.summary_stats,
  }
}

export async function fetchAdminUserCastles(uid: string, options?: RequestOptions): Promise<Castle[]> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/users/${encodeURIComponent(uid)}/castles`, {
    headers: authHeaders,
    signal: options?.signal,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'فشل جلب قلاع المستخدم')
  }
  const data = await res.json()
  const castles = data?.castles || (Array.isArray(data) ? data : [])
  return castles.map((c: any) => formatCastleFromApi(c))
}

export async function fetchAdminUsersCastles(options?: RequestOptions): Promise<AdminUserWithCastles[]> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/users-castles`, {
    headers: authHeaders,
    signal:  options?.signal,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'فشل جلب المستخدمين وقلاعهم')
  }
  const data = await res.json()
  const users = data?.users || []
  return users.map((u: any) => ({
    ...u,
    castles: (u.castles || []).map((c: any) => formatCastleFromApi(c)),
  }))
}

export async function disableElfForAllCastles(options?: RequestOptions): Promise<{
  status: string
  total_castles: number
  updated_count: number
  message: string
}> {
  const authHeaders = await getAuthHeader()
  const res = await fetch(`${getApiBaseUrl()}/api/admin/castles/disable-elf-all`, {
    method: 'POST',
    headers: { ...authHeaders, 'Content-Type': 'application/json' },
    signal:  options?.signal,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'فشل إيقاف مهمة العفريت لجميع القلاع')
  }
  return res.json()
}

