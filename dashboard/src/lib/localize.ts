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

  // 1b. Pending approval
  if (
    raw.includes('بانتظار موافقة الإدارة') ||
    raw.includes('بانتظار الموافقة') ||
    /pending/i.test(raw)
  ) {
    return t('dashboard.pendingApprovalStatus', 'بانتظار موافقة الإدارة')
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
      const daysMatch = suffix.match(/^(\d+)\s*(?:يوم|أيام|ايام|days?|gün)?$/i)
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

/**
 * Localizes backend and API server errors into the active language (AR, EN, TR).
 * Handles messages like:
 * - "البريد الإلكتروني لهذه القلعة مسجل بالفعل في النظام، لا يمكن إضافة نفس القلعة مرتين" -> apiErrors.castleAlreadyExists
 * - "البريد الإلكتروني لهذه القلعة مسجل بالفعل لقلعة أخرى" -> apiErrors.emailBelongsToAnotherCastle
 * - Quota, banning, and server state messages.
 */
export function localizeApiError(rawError?: string | null, t?: TFunction): string {
  if (!rawError) return ''
  const str = String(rawError).trim()
  if (!t) return str

  // 1. Castle duplicate email
  if (
    str.includes('مسجل بالفعل في النظام') ||
    str.includes('لا يمكن إضافة نفس القلعة مرتين') ||
    str.includes('already registered in the system') ||
    str.includes('already exists')
  ) {
    return t('apiErrors.castleAlreadyExists', 'البريد الإلكتروني لهذه القلعة مسجل بالفعل في النظام، لا يمكن إضافة نفس القلعة مرتين')
  }

  // 2. Email belongs to another castle
  if (
    str.includes('مسجل بالفعل لقلعة أخرى') ||
    str.includes('already registered to another castle')
  ) {
    return t('apiErrors.emailBelongsToAnotherCastle', 'البريد الإلكتروني لهذه القلعة مسجل بالفعل لقلعة أخرى')
  }

  // 3. User banned from adding castles
  if (
    str.includes('حسابك محظور من قبل الإدارة، لا يمكنك إضافة قلاع جديدة') ||
    (str.includes('محظور من قبل الإدارة') && str.includes('إضافة قلاع'))
  ) {
    return t('apiErrors.bannedCannotAddCastles', 'حسابك محظور من قبل الإدارة، لا يمكنك إضافة قلاع جديدة')
  }

  // 4. Pending approval trial plan
  if (
    str.includes('بانتظار موافقة الإدارة أولاً لتفعيل باقة التجربة') ||
    str.includes('لتفعيل باقة التجربة')
  ) {
    return t('apiErrors.pendingApprovalTrial', 'الحساب بانتظار موافقة الإدارة أولاً لتفعيل باقة التجربة')
  }

  // 5. Max castles during pending approval (10 max)
  if (
    str.includes('أثناء انتظار الموافقة') ||
    str.includes('10 قلاع كحد أقصى')
  ) {
    return t('apiErrors.pendingApprovalMaxCastles', 'وصلت للحد الأقصى المسموح به أثناء انتظار الموافقة (10 قلاع كحد أقصى)')
  }

  // 6. Plan quota exceeded
  if (
    str.includes('وصلت للحد الأقصى من القلاع المسموح بها في باقتك') ||
    str.includes('تم تجاوز الحد المسموح') ||
    str.includes('quota exceeded')
  ) {
    return t('apiErrors.planQuotaExceeded', 'وصلت للحد الأقصى من القلاع المسموح بها في باقتك')
  }

  // 7. Castle not found
  if (
    str.includes('القلعة غير موجودة') ||
    str.includes('Castle not found')
  ) {
    return t('apiErrors.castleNotFound', 'القلعة غير موجودة')
  }

  // 8. User not found
  if (
    str.includes('المستخدم غير موجود') ||
    str.includes('User not found')
  ) {
    return t('apiErrors.userNotFound', 'المستخدم غير موجود')
  }

  // 9. Account banned general
  if (
    str.includes('الحساب محظور من قبل الإدارة') ||
    str.includes('تم حظر حسابك') ||
    str.includes('account is banned')
  ) {
    return t('apiErrors.accountBanned', 'الحساب محظور من قبل الإدارة')
  }

  // 10. Game server connection failed
  if (
    str.includes('تعذر الاتصال بسيرفر اللعبة') ||
    str.includes('failed to connect to game server')
  ) {
    return t('apiErrors.gameServerConnectionFailed', 'تعذر الاتصال بسيرفر اللعبة')
  }

  // 11. Game server timeout
  if (
    str.includes('انتهت مهلة الاتصال بسيرفر اللعبة') ||
    (str.includes('timeout') && str.includes('سيرفر اللعبة'))
  ) {
    return t('apiErrors.gameServerTimeout', 'انتهت مهلة الاتصال بسيرفر اللعبة')
  }

  // 12. Update credentials failed
  if (str.includes('تعذر تحديث بيانات تسجيل الدخول للقلعة')) {
    return t('apiErrors.updateCredentialsFailed', 'تعذر تحديث بيانات تسجيل الدخول للقلعة')
  }

  // 13. Toggle active failed
  if (str.includes('تعذر تغيير حالة تفعيل القلعة')) {
    return t('apiErrors.toggleActiveFailed', 'تعذر تغيير حالة تفعيل القلعة')
  }

  // 14. Delete castle failed
  if (str.includes('تعذر حذف القلعة')) {
    return t('apiErrors.deleteCastleFailed', 'تعذر حذف القلعة')
  }

  // 15. Save castle failed in DB
  if (str.includes('تعذر حفظ القلعة في قاعدة البيانات')) {
    return t('apiErrors.saveCastleFailed', 'تعذر حفظ القلعة في قاعدة البيانات')
  }

  // 16. Update profile failed
  if (str.includes('تعذر تحديث الملف الشخصي')) {
    return t('apiErrors.updateProfileFailed', 'تعذر تحديث الملف الشخصي')
  }

  // 17. Castle suspended or inactive
  if (str.includes('لا يمكن تشغيل هذه القلعة لأنها معلقة أو غير مفعلة')) {
    return t('apiErrors.castleSuspendedOrInactive', 'لا يمكن تشغيل هذه القلعة لأنها معلقة أو غير مفعلة ضمن باقتك الحالية')
  }

  // 18. Account not registered
  if (str.includes('هذا الحساب غير مسجل في هذا النظام')) {
    return t('apiErrors.accountNotRegistered', 'هذا الحساب غير مسجل في هذا النظام')
  }

  // 19. Access denied
  if (
    str.includes('وصول مرفوض: لا تملك صلاحيات إدارة النظام') ||
    str.includes('لا تملك صلاحيات')
  ) {
    return t('apiErrors.accessDenied', 'وصول مرفوض: لا تملك صلاحيات إدارة النظام')
  }

  // 20. Server deploying / maintenance
  if (
    str.includes('السيرفر في وضع التحديث حالياً') ||
    str.includes('يرجى الانتظار حتى اكتمال التحديث')
  ) {
    return t('accounts.deployingToast', 'جاري رفع التغييرات إلى السيرفر... يرجى الانتظار حتى اكتمال التحديث واستئناف البوت تلقائياً')
  }

  return str
}

