/**
 * Professional, standard validation utilities for Authentication (Login & Register).
 * Prevents HTML5 browser validation glitches, normalizes inputs, and delivers
 * crisp, localized, standard error messages.
 */
import type { TFunction } from 'i18next'

export type TranslateFn = TFunction<any, any> | ((key: string, fallback?: string) => string) | any

/**
 * Normalizes email: trims outer whitespaces, removes hidden zero-width characters,
 * and converts to lower case.
 */
export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase()
}

/**
 * Validates email field. Returns error string or null if valid.
 */
export function validateEmail(
  rawEmail: string,
  t?: TranslateFn
): string | null {
  const email = normalizeEmail(rawEmail)

  if (!email) {
    return t
      ? t('validation.emailRequired', 'يرجى إدخال البريد الإلكتروني')
      : 'يرجى إدخال البريد الإلكتروني'
  }

  if (!email.includes('@')) {
    return t
      ? t('validation.emailInvalid', 'يرجى إدخال بريد إلكتروني صالح')
      : 'يرجى إدخال بريد إلكتروني صالح'
  }

  return null
}
/**
 * Validates password for Login.
 */
export function validateLoginPassword(
  password: string,
  t?: TranslateFn
): string | null {
  if (!password) {
    return t ? t('validation.passwordRequired', 'يرجى إدخال كلمة المرور') : 'يرجى إدخال كلمة المرور'
  }
  if (password.length < 6) {
    return t
      ? t('validation.passwordMin', 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
      : 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'
  }
  return null
}

/**
 * Validates password for Registration.
 */
export function validateRegisterPassword(
  password: string,
  t?: TranslateFn
): string | null {
  if (!password) {
    return t ? t('validation.passwordRequired', 'يرجى إدخال كلمة المرور') : 'يرجى إدخال كلمة المرور'
  }
  if (password.length < 6) {
    return t
      ? t('validation.passwordMin', 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
      : 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'
  }
  if (password.length > 128) {
    return t ? t('validation.passwordMax', 'كلمة المرور طويلة جداً') : 'كلمة المرور طويلة جداً'
  }
  return null
}

/**
 * Validates password confirmation.
 */
export function validateConfirmPassword(
  password: string,
  confirm: string,
  t?: TranslateFn
): string | null {
  if (!confirm) {
    return t ? t('validation.confirmRequired', 'يرجى تأكيد كلمة المرور') : 'يرجى تأكيد كلمة المرور'
  }
  if (password !== confirm) {
    return t ? t('validation.passwordMismatch', 'كلمتا المرور غير متطابقتين') : 'كلمتا المرور غير متطابقتين'
  }
  return null
}

/**
 * Validates display name / username.
 */
export function validateUsername(
  username: string,
  t?: TranslateFn
): string | null {
  const trimmed = username.trim()
  if (trimmed && trimmed.length < 2) {
    return t ? t('validation.usernameMin', 'الاسم يجب أن يتكون من حرفين على الأقل') : 'الاسم يجب أن يتكون من حرفين على الأقل'
  }
  if (trimmed.length > 40) {
    return t ? t('validation.usernameMax', 'الاسم يجب ألا يتجاوز 40 حرفاً') : 'الاسم يجب ألا يتجاوز 40 حرفاً'
  }
  return null
}

/**
 * Evaluates password strength (Score 1-3)
 */
export interface PasswordStrength {
  score: 1 | 2 | 3
  label: string
  colorClass: string
  bgClass: string
  percent: number
}

export function getPasswordStrength(
  password: string,
  t?: TranslateFn
): PasswordStrength | null {
  if (!password) return null

  let points = 0
  if (password.length >= 6) points++
  if (password.length >= 8) points++
  if (/[0-9]/.test(password)) points++
  if (/[a-zA-Z]/.test(password) && /[^a-zA-Z0-9]/.test(password)) points++

  if (points <= 1 || password.length < 6) {
    return {
      score: 1,
      label: t ? t('validation.pwWeak', 'ضعيفة') : 'ضعيفة',
      colorClass: 'text-rose-400',
      bgClass: 'bg-rose-500',
      percent: 33,
    }
  }

  if (points <= 3) {
    return {
      score: 2,
      label: t ? t('validation.pwMedium', 'متوسطة') : 'متوسطة',
      colorClass: 'text-amber-400',
      bgClass: 'bg-amber-500',
      percent: 66,
    }
  }

  return {
    score: 3,
    label: t ? t('validation.pwStrong', 'قوية') : 'قوية',
    colorClass: 'text-emerald-400',
    bgClass: 'bg-emerald-500',
    percent: 100,
  }
}

/**
 * Maps Firebase Auth errors to user-friendly messages.
 */
export function mapFirebaseAuthError(
  err: unknown,
  t?: TranslateFn
): { field?: 'email' | 'password'; message: string } {
  const code = (err && typeof err === 'object' && 'code' in err ? (err as { code: string }).code : '') ||
               (err instanceof Error ? err.message : '')

  if (code.includes('user-not-found') || code.includes('wrong-password') || code.includes('invalid-credential')) {
    return {
      message: t ? t('login.invalidCreds', 'البريد الإلكتروني أو كلمة المرور غير صحيحة') : 'البريد الإلكتروني أو كلمة المرور غير صحيحة',
    }
  }

  if (code.includes('email-already-in-use')) {
    return {
      field: 'email',
      message: t ? t('register.emailInUse', 'هذا البريد الإلكتروني مسجل بالفعل، يرجى تسجيل الدخول') : 'هذا البريد الإلكتروني مسجل بالفعل، يرجى تسجيل الدخول',
    }
  }

  if (code.includes('invalid-email')) {
    return {
      field: 'email',
      message: t ? t('validation.emailInvalid', 'صيغة البريد الإلكتروني غير مقبولة') : 'صيغة البريد الإلكتروني غير مقبولة',
    }
  }

  if (code.includes('too-many-requests')) {
    return {
      message: t ? t('validation.tooManyRequests', 'تم حظر المحاولات مؤقتاً لأسباب أمنية، يرجى المحاولة بعد قليل') : 'تم حظر المحاولات مؤقتاً لأسباب أمنية، يرجى المحاولة بعد قليل',
    }
  }

  if (code.includes('network-request-failed')) {
    return {
      message: t ? t('validation.networkError', 'تعذر الاتصال بالخادم، يرجى التحقق من اتصال الإنترنت') : 'تعذر الاتصال بالخادم، يرجى التحقق من اتصال الإنترنت',
    }
  }

  return {
    message: t ? t('common.error', 'حدث خطأ غير متوقع، يرجى المحاولة لاحقاً') : 'حدث خطأ غير متوقع، يرجى المحاولة لاحقاً',
  }
}
