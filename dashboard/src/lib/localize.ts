import type { TFunction } from 'i18next'

/**
 * Localizes subscription plan names dynamically across AR, EN, and TR.
 * Handles:
 * - "باقة المشرف الأعلى (SuperAdmin)", "باقة المشرف الأعلى", "SuperAdmin" -> plans.superAdmin
 * - "X حساب" / "X accounts" / "X hesap" -> plans.accountsCount (e.g. "20 حساب" in AR, "20 Accounts" in EN, "20 Hesap" in TR)
 * - "مجاني" / "Free" -> plans.free
 * - "تجريبي" / "Trial" -> plans.trial
 */
export function localizePlanName(planName?: string | null, t?: TFunction): string {
  if (!planName) return '—'
  const raw = planName.trim()
  if (!t) return raw

  // 1. SuperAdmin plan
  if (
    raw.includes('المشرف الأعلى') ||
    raw.includes('المشرفة الاعلى') ||
    /superadmin/i.test(raw)
  ) {
    return t('plans.superAdmin', 'باقة المشرف الأعلى')
  }

  // 2. Standalone expired
  if (/^(منتهي|منتهي الصلاحية|expired|süresi doldu)$/i.test(raw)) {
    return t('dashboard.expiredBadge', 'منتهي')
  }

  // 3. Free plan
  if (/^(مجاني|free|ücretsiz)$/i.test(raw)) {
    return t('plans.free', 'مجاني')
  }

  // 4. Trial plan
  if (/^(تجريبي|trial|deneme)$/i.test(raw)) {
    return t('plans.trial', 'تجريبي')
  }

  // 5. Account count with optional bracketed status (e.g. "25 حساب (منتهي)", "1 حساب", "5 accounts (expired)")
  const bracketMatch = raw.match(/^(\d+)\s*(?:حساب|accounts?|hesap)?(?:\s*\((.*?)\))?$/i)
  if (bracketMatch) {
    const count = parseInt(bracketMatch[1], 10)
    const suffix = bracketMatch[2]?.trim()

    const baseText = t('plans.accountsCount', {
      count,
      defaultValue: count === 1
        ? `1 ${t('accounts.accountUnit', 'حساب')}`
        : `${count} ${t('accounts.accountUnit', 'حساب')}`
    })

    if (suffix) {
      if (/^(منتهي|منتهي الصلاحية|expired|süresi doldu)$/i.test(suffix)) {
        return baseText
      }
      const daysMatch = suffix.match(/^(\d+)\s*(?:يوم|days?|gün)?$/i)
      if (daysMatch) {
        const days = parseInt(daysMatch[1], 10)
        return `${baseText} (${t('dashboard.daysRemaining', { count: days })})`
      }
      return `${baseText} (${suffix})`
    }
    return baseText
  }

  // 6. Fallback: strip any (منتهي) and replace known tokens in custom strings
  let result = raw.replace(/\s*\((?:منتهي|منتهي الصلاحية|expired|süresi doldu)\)/gi, '').trim()
  if (result.includes('منتهي')) {
    result = result.replace(/منتهي/g, t('dashboard.expiredBadge', 'منتهي'))
  }
  if (result.includes('حساب')) {
    const unit = t('accounts.accountUnit', 'حساب')
    result = result.replace(/حساب/g, unit)
  }

  return result.trim()
}

/**
 * Localizes known administrative usernames (e.g. "المشرف الأعلى (SuperAdmin)")
 */
export function localizeUsername(username?: string | null, t?: TFunction): string {
  if (!username) return ''
  const raw = username.trim()

  if (
    raw.includes('المشرف الأعلى') ||
    raw.includes('المشرفة الاعلى') ||
    raw === 'SuperAdmin' ||
    raw === 'Super Admin'
  ) {
    return t ? t('roles.superAdmin', 'المشرف الأعلى') : raw
  }

  return raw
}
