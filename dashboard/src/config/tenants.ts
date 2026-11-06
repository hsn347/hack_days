// ══════════════════════════════════════════════════════════════════════════════
// 🏢 سجل إعدادات التجار والنطاقات المتعددة (Multi-Domain Tenants Registry)
// ══════════════════════════════════════════════════════════════════════════════
// هذا هو الملف المركزي للواجهة حيث يمكنك إضافة أي دومين أو تاجر جديد في ثوانٍ!
// فقط أضف كائن جديد في مصفوفة MERCHANTS_CONFIG أدناه، وسيتولى الموقع الباقي تلقائياً.

export interface TenantConfig {
  /** معرف فريد للتاجر (حروف إنجليزية صغيرة بدون مسافات) */
  id: string
  /** قائمة الدومينات المرتبطة بهذا التاجر */
  domains: string[]
  /** اسم البوت المعروض للمستخدمين */
  brandName: string
  /** وصف البوت باللغات الثلاث */
  tagline: {
    ar: string
    en: string
    tr: string
  }
  /** رابط شعار البوت (يمكن وضع الصورة في مجلد public مثلاً /logos/nurjan.png) */
  logoUrl: string
  /** أيقونة المتصفح (Favicon) */
  faviconUrl?: string
  /**
   * اللون الأساسي للتاجر بصيغة HEX (مثلاً #2563eb للأزرق، أو #8b5cf6 للبنفسجي، أو #d97706 للذهبي)
   * سيتم تطبيق هذا اللون تلقائياً على كامل الموقع والأزرار والشارات والإضاءات
   */
  primaryColor: string
  /** البريد الإلكتروني لمشرف هذا الدومين (Merchant Admin) */
  adminEmail: string
  /** اللغة الافتراضية للزوار عند الدخول عبر هذا الدومين لأول مرة ('ar' | 'en' | 'tr') */
  defaultLanguage?: 'ar' | 'en' | 'tr'
}

// ─── 1. الدومين الرئيسي الافتراضي (IBRA BOT - المشرف الأعلى) ───────────────────
export const DEFAULT_TENANT: TenantConfig = {
  id: 'main',
  domains: ['localhost', '127.0.0.1', 'ibrabot.com', '187.7.79.122', 'ibraabot.online', 'www.ibraabot.online'],
  brandName: 'IBRA BOT',
  defaultLanguage: 'ar',
  tagline: {
    ar: 'أول بوت عربي',
    en: 'The First Arabic Bot',
    tr: 'İlk Arapça Bot',
  },
  logoUrl: '/logo.png?v=2',
  faviconUrl: '/favicon.ico',
  primaryColor: '#10b981', // اللون الزمردي الأخضر الأصلي
  adminEmail: 'ibraboths@gmail.com',
}

// ─── 2. قائمة التجار والموزعين (أضف أي تاجر أو دومين جديد هنا) ──────────────────
export const MERCHANTS_CONFIG: TenantConfig[] = [
  {
    id: 'nurjan',
    domains: ['nurjanbot.online', 'www.nurjanbot.online'],
    brandName: 'Nurjan bot',
    defaultLanguage: 'tr', // اللغة الافتراضية لدومين نورجان هي التركية
    tagline: {
      ar: '',
      en: '',
      tr: '',
    },
    logoUrl: '/nurjan_logo.jpeg',
    faviconUrl: '/nurjan_logo.jpeg',
    primaryColor: '#d49835', // ذهبي ملكي متطابق مع الشعار
    adminEmail: 'nurjan12ddsw2@gmail.com',
  },
  {
    id: 'sharkgo',
    domains: ['sharkgo.online', 'www.sharkgo.online'],
    brandName: 'SHARK GO',
    defaultLanguage: 'ar',
    tagline: {
      ar: 'بوت جمع الذهب والتطوير',
      en: 'Gold Harvester & Upgrade Bot',
      tr: 'Altın Toplama & Geliştirme Botu',
    },
    logoUrl: '/logo.png?v=2',
    faviconUrl: '/favicon.ico',
    primaryColor: '#eab308',
    adminEmail: 'ibraboths@gmail.com',
  },
  // ─── مثال لإضافة تاجر جديد لاحقاً: ───
  /*
  {
    id: 'vipbot',
    domains: ['vipbot.net', 'www.vipbot.net'],
    brandName: 'VIP BOT',
    tagline: {
      ar: 'أقوى بوت للمعارك والتحالفات',
      en: 'The Ultimate Battle & Alliance Bot',
      tr: 'En Güçlü Savaş Botu',
    },
    logoUrl: '/logo.png?v=2',
    primaryColor: '#8b5cf6', // بنفسجي ملكي
    adminEmail: 'vip_admin@gmail.com',
  },
  */
]

/**
 * دالة مساعدة لجلب إعدادات التاجر استناداً إلى اسم النطاق (Hostname)
 * تدعم الفحص التلقائي لـ window.location.hostname وأيضاً معلمة الاختبار السريع ?tenant= أو ?domain=
 */
export function getTenantByHostname(hostname: string): TenantConfig {
  let cleanHost = hostname.toLowerCase().trim().replace(/^www\./, '')

  // دعم الاختبار المحلي السريع عبر رابط المتصفح أو التخزين المحلي
  if (typeof window !== 'undefined') {
    try {
      const searchParams = new URLSearchParams(window.location.search)
      const qTenant = searchParams.get('tenant')
      const qDomain = searchParams.get('domain')

      if (qTenant) {
        localStorage.setItem('dev_selected_tenant', qTenant)
        const byId = MERCHANTS_CONFIG.find(m => m.id.toLowerCase() === qTenant.toLowerCase().trim())
        if (byId) return byId
      }
      if (qDomain) {
        cleanHost = qDomain.toLowerCase().trim().replace(/^www\./, '')
      }

      // على البيئة المحلية: استعادة التاجر المختار سابقاً (إن وُجد)
      const isLocal = cleanHost === 'localhost' || cleanHost === '127.0.0.1'
      if (isLocal) {
        const savedTenant = localStorage.getItem('dev_selected_tenant')
        if (savedTenant === 'main') {
          return DEFAULT_TENANT
        }
        if (savedTenant) {
          const bySaved = MERCHANTS_CONFIG.find(m => m.id.toLowerCase() === savedTenant.toLowerCase().trim())
          if (bySaved) return bySaved
        }
        return DEFAULT_TENANT
      }
    } catch {
      // ignore
    }
  }

  // البحث في قائمة التجار
  const found = MERCHANTS_CONFIG.find(m =>
    m.domains.some(d => {
      const cleanD = d.toLowerCase().trim().replace(/^www\./, '').split(':')[0]
      return cleanHost === cleanD || cleanHost.endsWith('.' + cleanD)
    }) || cleanHost.includes(m.id.toLowerCase())
  )

  return found || DEFAULT_TENANT
}

/**
 * الحصول على إعدادات التاجر الحالي النشط بناءً على رابط المتصفح
 */
export function getCurrentTenant(): TenantConfig {
  const host = typeof window !== 'undefined' ? window.location.hostname : ''
  return getTenantByHostname(host)
}

/**
 * الحصول على اللغة الافتراضية النشطة للنطاق الحالي:
 * 1. إذا كان المستخدم قد اختار لغة يدوياً صراحةً لهذا النطاق، يُحترم اختياره.
 * 2. إذا لم يقم المستخدم باختيار يدوي صريح، تؤخذ اللغة الافتراضية المحددة في إعدادات النطاق
 *    (مثل التركية 'tr' لنورجان، والعربية 'ar' للرئيسي).
 */
export function getInitialLanguage(): 'ar' | 'en' | 'tr' {
  if (typeof window === 'undefined') return 'ar'
  try {
    const tenant = getCurrentTenant()
    const tenantKey = tenant.id || 'main'

    // 1. فحص الاختيار اليدوي الصريح لهذا النطاق
    const isManualForTenant = localStorage.getItem(`osmanli_lang_manual_${tenantKey}`) === 'true'
    const savedForTenant = localStorage.getItem(`osmanli_lang_${tenantKey}`)
    if (isManualForTenant && savedForTenant && (savedForTenant === 'ar' || savedForTenant === 'en' || savedForTenant === 'tr')) {
      return savedForTenant as 'ar' | 'en' | 'tr'
    }

    // 2. فحص لغة النطاق الافتراضية
    if (tenant.defaultLanguage && (tenant.defaultLanguage === 'ar' || tenant.defaultLanguage === 'en' || tenant.defaultLanguage === 'tr')) {
      return tenant.defaultLanguage
    }
  } catch {
    // ignore
  }
  return 'ar'
}

/**
 * دالة التحقق الصارم من انتماء المستخدم للنطاق الحالي (Tenant Isolation).
 * تمنع تماماً دخول حسابات النظام الأول (الرئيسي) في نطاقات التجار والعكس صحيح.
 */
export function isUserAllowedForTenant(
  user: { email?: string; tenant_domain?: string; role?: string } | null,
  tenant: TenantConfig
): boolean {
  if (!user || !user.email) return false

  const email = user.email.trim().toLowerCase()
  const rawUserDomain = (user.tenant_domain || '').trim().toLowerCase().replace(/^www\./, '')

  // 1. إذا كان النظام المعروض تابعاً لتاجر (مثل Nurjan bot):
  if (tenant.id !== 'main') {
    // أ) مشرف التاجر مصرح له بالدخول لنظامه
    if (email === tenant.adminEmail.trim().toLowerCase()) {
      return true
    }

    // ب) حساب المشرف الأعلى وحسابات مشرفي التجار الآخرين غير مصرح لهم بنظام هذا التاجر
    if (email === DEFAULT_TENANT.adminEmail.trim().toLowerCase()) {
      return false
    }
    if (MERCHANTS_CONFIG.some(m => m.id !== tenant.id && m.adminEmail.trim().toLowerCase() === email)) {
      return false
    }

    // ج) حسابات العملاء العاديين: يجب أن تكون مسجلة حصراً تحت هذا النطاق
    const merchantDomains = tenant.domains.map(d => d.trim().toLowerCase().replace(/^www\./, ''))
    merchantDomains.push(tenant.id.toLowerCase())

    if (!rawUserDomain) {
      // أي حساب مسجل بدون نطاق هو حساب تابع للنظام الرئيسي وممنوع من الدخول هنا
      return false
    }

    return merchantDomains.includes(rawUserDomain)
  }

  // 2. إذا كان النظام المعروض هو النظام الرئيسي الافتراضي (IBRA BOT / main):
  if (tenant.id === 'main') {
    // أ) المشرف الأعلى مصرح له بالدخول للنظام الرئيسي
    if (email === DEFAULT_TENANT.adminEmail.trim().toLowerCase()) {
      return true
    }

    // ب) مشرفو التجار ممنوعون من الدخول كحساب عادي في النظام الرئيسي
    if (MERCHANTS_CONFIG.some(m => m.adminEmail.trim().toLowerCase() === email)) {
      return false
    }

    // ج) أي حساب مسجل تحت دومين تاجر ممنوع من الدخول في النظام الرئيسي
    const allMerchantDomains = MERCHANTS_CONFIG.flatMap(m => [
      ...m.domains.map(d => d.trim().toLowerCase().replace(/^www\./, '')),
      m.id.toLowerCase()
    ])

    if (rawUserDomain && allMerchantDomains.includes(rawUserDomain)) {
      return false
    }

    // الحسابات المسموح بها في النظام الرئيسي: فارغة أو main أو تابعة لنطاقات النظام الرئيسي
    const mainDomains = DEFAULT_TENANT.domains.map(d => d.trim().toLowerCase().replace(/^www\./, ''))
    return !rawUserDomain || rawUserDomain === 'main' || mainDomains.includes(rawUserDomain)
  }

  return false
}

