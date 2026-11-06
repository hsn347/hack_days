// ══════════════════════════════════════════════════════════════════
// 👥 إدارة الحسابات المحفوظة والتنقل السريع (Multi-Account Manager)
// ══════════════════════════════════════════════════════════════════

import { getCurrentTenant } from '../config/tenants'

export interface SavedAccount {
  uid: string
  email: string
  username: string
  role: string
  tenantId?: string
  hasSavedPassword: boolean
  secretToken?: string
  lastUsedAt: number
  planName?: string
}

function getStorageKey(): string {
  if (typeof window === 'undefined') return 'ibra_saved_accounts_main'
  try {
    const tenant = getCurrentTenant()
    return `ibra_saved_accounts_${tenant.id || 'main'}`
  } catch {
    return 'ibra_saved_accounts_main'
  }
}

const CIPHER_KEY = 'ibra_bot_salt_k9x_'

// تشفير وفك تشفير خفيف وآمن للمتصفح لحفظ كلمات المرور محلياً دون تخزينها كنص صريح
function encryptToken(plain: string): string {
  try {
    const chars = plain.split('').map((c, i) =>
      c.charCodeAt(0) ^ CIPHER_KEY.charCodeAt(i % CIPHER_KEY.length)
    )
    return btoa(String.fromCharCode(...chars))
  } catch {
    return btoa(plain)
  }
}

function decryptToken(cipher: string): string {
  try {
    const decoded = atob(cipher)
    const chars = decoded.split('').map((c, i) =>
      c.charCodeAt(0) ^ CIPHER_KEY.charCodeAt(i % CIPHER_KEY.length)
    )
    return String.fromCharCode(...chars)
  } catch {
    return ''
  }
}

/**
 * جلب جميع الحسابات المحفوظة على هذا المتصفح والخاصة بالنطاق الحالي فقط
 */
export function getSavedAccounts(): SavedAccount[] {
  if (typeof window === 'undefined') return []
  try {
    const key = getStorageKey()
    let raw = localStorage.getItem(key)
    // 🛡️ التوافق التام للدخول الفوري: فحص المفتاح العام القديم ibra_saved_accounts أو ibra_saved_accounts_main
    if (!raw) {
      raw = localStorage.getItem('ibra_saved_accounts') || localStorage.getItem('ibra_saved_accounts_main')
      if (raw) {
        try {
          localStorage.setItem(key, raw)
        } catch {}
      }
    }
    if (!raw) return []
    const parsed = JSON.parse(raw)
    const currentTenantId = getCurrentTenant().id
    if (Array.isArray(parsed)) {
      return parsed
        .filter(a => !a.tenantId || a.tenantId === currentTenantId || currentTenantId === 'main')
        .sort((a, b) => (b.lastUsedAt || 0) - (a.lastUsedAt || 0))
    }
  } catch (err) {
    console.warn('Failed to parse saved accounts:', err)
  }
  return []
}

/**
 * حفظ أو تحديث بيانات حساب في الذاكرة المحلية
 */
export function saveOrUpdateAccount(
  account: {
    uid: string
    email: string
    username?: string
    role?: string
    planName?: string
  },
  password?: string
): void {
  if (typeof window === 'undefined' || !account.email) return

  const cleanEmail = account.email.trim().toLowerCase()
  const accounts = getSavedAccounts()
  const existingIdx = accounts.findIndex(a => a.email.toLowerCase() === cleanEmail)

  let secretToken = existingIdx >= 0 ? accounts[existingIdx].secretToken : undefined
  let hasSavedPassword = existingIdx >= 0 ? accounts[existingIdx].hasSavedPassword : false

  if (password && password.trim()) {
    secretToken = encryptToken(password)
    hasSavedPassword = true
  }

  const currentTenantId = getCurrentTenant().id

  const updatedEntry: SavedAccount = {
    uid: account.uid,
    email: cleanEmail,
    username: account.username || cleanEmail.split('@')[0],
    role: account.role || (cleanEmail === 'ibraboths@gmail.com' ? 'admin' : 'user'),
    tenantId: currentTenantId,
    hasSavedPassword,
    secretToken,
    lastUsedAt: Date.now(),
    planName: account.planName || (existingIdx >= 0 ? accounts[existingIdx].planName : undefined),
  }

  if (existingIdx >= 0) {
    accounts[existingIdx] = updatedEntry
  } else {
    accounts.unshift(updatedEntry)
  }

  // الاحتفاظ بحد أقصى 25 حساب لتجنب امتلاء الذاكرة
  const trimmed = accounts.slice(0, 25)
  try {
    const serialized = JSON.stringify(trimmed)
    localStorage.setItem(getStorageKey(), serialized)
    localStorage.setItem('ibra_saved_accounts', serialized)
  } catch (e) {
    console.warn('Failed to save accounts to storage:', e)
  }
}

/**
 * استخراج بيانات الدخول لحساب محفوظ (للتبديل بنقرة واحدة)
 */
export function getAccountCredentials(email: string): { email: string; password?: string } | null {
  const cleanEmail = email.trim().toLowerCase()
  const accounts = getSavedAccounts()
  const target = accounts.find(a => a.email.toLowerCase() === cleanEmail)
  if (!target) return null

  let password: string | undefined
  if (target.secretToken) {
    password = decryptToken(target.secretToken)
  }

  return {
    email: target.email,
    password,
  }
}

/**
 * تحديث توقيت آخر استخدام لحساب معين
 */
export function updateAccountLastUsed(email: string): void {
  const cleanEmail = email.trim().toLowerCase()
  const accounts = getSavedAccounts()
  const target = accounts.find(a => a.email.toLowerCase() === cleanEmail)
  if (target) {
    target.lastUsedAt = Date.now()
    try {
      localStorage.setItem(getStorageKey(), JSON.stringify(accounts))
    } catch {
      // ignore
    }
  }
}

/**
 * حذف حساب محدد من قائمة الحسابات المحفوظة
 */
export function removeSavedAccount(email: string): SavedAccount[] {
  const cleanEmail = email.trim().toLowerCase()
  const accounts = getSavedAccounts().filter(a => a.email.toLowerCase() !== cleanEmail)
  try {
    localStorage.setItem(getStorageKey(), JSON.stringify(accounts))
  } catch (e) {
    console.warn('Failed to remove account:', e)
  }
  return accounts
}
