import React, { createContext, useContext, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { getTenantByHostname, DEFAULT_TENANT, TenantConfig } from '../config/tenants'
import { useAppStore } from '../store/appStore'

interface TenantContextType {
  tenant: TenantConfig
  isCustomTenant: boolean
  brandName: string
  tagline: string
  logoUrl: string
  faviconUrl: string
  primaryColor: string
  domain: string
}

const TenantContext = createContext<TenantContextType>({
  tenant: DEFAULT_TENANT,
  isCustomTenant: false,
  brandName: DEFAULT_TENANT.brandName,
  tagline: DEFAULT_TENANT.tagline.ar,
  logoUrl: DEFAULT_TENANT.logoUrl,
  faviconUrl: DEFAULT_TENANT.faviconUrl || '/favicon.ico',
  primaryColor: DEFAULT_TENANT.primaryColor,
  domain: 'ibrabot.com',
})

export function useTenant(): TenantContextType {
  return useContext(TenantContext)
}

function hexToRgb(hex: string): string {
  try {
    let clean = hex.replace('#', '').trim()
    if (clean.length === 3) {
      clean = clean.split('').map(c => c + c).join('')
    }
    const num = parseInt(clean, 16)
    const r = (num >> 16) & 255
    const g = (num >> 8) & 255
    const b = num & 255
    return `${r}, ${g}, ${b}`
  } catch {
    return '16, 185, 129' // Fallback emerald
  }
}

/**
 * حساب درجات الألوان المختلفة للثيم (فاتح، داكن، شفاف)
 */
function hexToHsl(hex: string): [number, number, number] {
  let clean = hex.replace('#', '').trim()
  if (clean.length === 3) clean = clean.split('').map(c => c + c).join('')
  const r = parseInt(clean.substring(0, 2), 16) / 255
  const g = parseInt(clean.substring(2, 4), 16) / 255
  const b = parseInt(clean.substring(4, 6), 16) / 255

  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  let h = 0, s = 0, l = (max + min) / 2

  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break
      case g: h = (b - r) / d + 2; break
      case b: h = (r - g) / d + 4; break
    }
    h /= 6
  }
  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)]
}

function hslToHex(h: number, s: number, l: number): string {
  l /= 100
  const a = (s * Math.min(l, 1 - l)) / 100
  const f = (n: number) => {
    const k = (n + h / 30) % 12
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(255 * color).toString(16).padStart(2, '0')
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

function generatePalette(hex: string): Record<string, string> {
  const [h, s, l] = hexToHsl(hex)
  return {
    '50': hslToHex(h, Math.min(s, 70), 96),
    '100': hslToHex(h, Math.min(s, 75), 90),
    '200': hslToHex(h, Math.min(s, 80), 80),
    '300': hslToHex(h, s, 68),
    '400': hslToHex(h, s, 58),
    '500': hex,
    '600': hslToHex(h, s, Math.max(15, l - 8)),
    '700': hslToHex(h, s, Math.max(12, l - 18)),
    '800': hslToHex(h, s, Math.max(10, l - 28)),
    '900': hslToHex(h, s, Math.max(8, l - 36)),
    '950': hslToHex(h, s, Math.max(6, l - 44)),
  }
}

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const { i18n } = useTranslation()
  const searchStr = typeof window !== 'undefined' ? window.location.search : ''
  const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost'

  const tenant = useMemo(() => {
    return getTenantByHostname(hostname)
  }, [hostname, searchStr])

  const isCustomTenant = tenant.id !== DEFAULT_TENANT.id
  const lang = (i18n.language || 'ar').toLowerCase()
  const localizedTagline =
    lang === 'tr' ? tenant.tagline.tr : lang === 'en' ? tenant.tagline.en : tenant.tagline.ar

  // ─── ضبط اللغة الافتراضية للتاجر تلقائياً (مثل التركية لدومين نورجان) ما لم يختر المستخدم لغة أخرى ───
  useEffect(() => {
    if (tenant.defaultLanguage) {
      const tenantKey = tenant.id || 'main'
      const isManual = typeof window !== 'undefined'
        ? localStorage.getItem(`osmanli_lang_manual_${tenantKey}`) === 'true'
        : false

      if (!isManual) {
        if (i18n.language !== tenant.defaultLanguage) {
          i18n.changeLanguage(tenant.defaultLanguage)
        }
        if (useAppStore.getState().language !== tenant.defaultLanguage) {
          useAppStore.setState({ language: tenant.defaultLanguage })
        }
      }
    }
  }, [tenant.id, tenant.defaultLanguage, i18n])

  // ─── تطبيق الهوية البصرية والألوان ديناميكياً ─────────────────────────────
  useEffect(() => {
    if (typeof document === 'undefined') return

    const primary = tenant.primaryColor || '#10b981'
    const primaryRgb = hexToRgb(primary)
    const shades = generatePalette(primary)
    const primaryDark = shades['600']
    const primaryLight = shades['400']

    const root = document.documentElement

    // حقن متغيرات الألوان التفاعلية الأساسية
    root.style.setProperty('--theme-primary', primary)
    root.style.setProperty('--theme-primary-rgb', primaryRgb)
    root.style.setProperty('--theme-primary-hover', primaryDark)
    root.style.setProperty('--theme-primary-light', primaryLight)
    root.style.setProperty('--theme-primary-dark', shades['700'])

    // حقن تدرجات الألوان لكامل الموقع في وضعي النهار والليل (مع ترك ألوان الحالات مثل الأخضر emerald دون تعديل)
    Object.entries(shades).forEach(([shade, val]) => {
      root.style.setProperty(`--theme-primary-${shade}`, val)
      root.style.setProperty(`--color-primary-${shade}`, val)
      root.style.removeProperty(`--color-emerald-${shade}`)
    })

    // تحديث إشعاع الظلال المحيطية لهوية البراند
    root.style.setProperty('--shadow-glow', `0 0 20px rgba(${primaryRgb}, 0.35)`)

    // تحديث عنوان الصفحة بالمتصفح
    if (tenant.tagline?.ar) {
      document.title = `${tenant.brandName} — ${tenant.tagline.ar}`
    } else {
      document.title = tenant.brandName
    }

    // تحديث Favicon إذا كان مخصصاً
    if (tenant.faviconUrl) {
      let link: HTMLLinkElement | null = document.querySelector("link[rel*='icon']")
      if (!link) {
        link = document.createElement('link')
        link.rel = 'shortcut icon'
        document.head.appendChild(link)
      }
      link.href = tenant.faviconUrl
    }

    // تحديث اسم وأيقونة الجوال عند إضافة التطبيق للشاشة الرئيسية (PWA / Add to Home Screen)
    const appTitleMeta = document.querySelector('meta[name="apple-mobile-web-app-title"]')
    if (appTitleMeta) appTitleMeta.setAttribute('content', tenant.brandName)
    const appNameMeta = document.querySelector('meta[name="application-name"]')
    if (appNameMeta) appNameMeta.setAttribute('content', tenant.brandName)

    if (tenant.logoUrl) {
      const appleIcons = document.querySelectorAll('link[rel*="apple-touch-icon"]')
      appleIcons.forEach(el => el.setAttribute('href', tenant.logoUrl))
    }

    // 📱 تحديث Web App Manifest ديناميكياً لتثبيت التطبيق بالاسم والأيقونة والألوان الخاصة بهذا التاجر
    try {
      const mime = tenant.logoUrl.endsWith('.png') ? 'image/png' : 'image/jpeg'
      const dynamicManifest = {
        name: tenant.brandName,
        short_name: tenant.brandName,
        description: tenant.tagline?.ar || `${tenant.brandName}`,
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait-primary',
        background_color: '#0a0f0a',
        theme_color: tenant.primaryColor || '#10b981',
        lang: 'ar',
        dir: 'rtl',
        categories: ['utilities', 'games', 'productivity'],
        icons: [
          {
            src: tenant.logoUrl,
            sizes: '192x192',
            type: mime,
            purpose: 'any',
          },
          {
            src: tenant.logoUrl,
            sizes: '512x512',
            type: mime,
            purpose: 'any',
          },
          {
            src: tenant.logoUrl,
            sizes: '192x192',
            type: mime,
            purpose: 'maskable',
          },
          {
            src: tenant.logoUrl,
            sizes: '512x512',
            type: mime,
            purpose: 'maskable',
          },
        ],
      }

      const manifestBlob = new Blob([JSON.stringify(dynamicManifest)], { type: 'application/manifest+json' })
      const manifestBlobUrl = URL.createObjectURL(manifestBlob)
      let manifestLink = document.querySelector<HTMLLinkElement>('link[rel="manifest"]')
      if (!manifestLink) {
        manifestLink = document.createElement('link')
        manifestLink.rel = 'manifest'
        document.head.appendChild(manifestLink)
      }
      manifestLink.href = manifestBlobUrl
    } catch {
      // ignore
    }
  }, [tenant])

  const contextValue: TenantContextType = {
    tenant,
    isCustomTenant,
    brandName: tenant.brandName,
    tagline: localizedTagline,
    logoUrl: tenant.logoUrl,
    faviconUrl: tenant.faviconUrl || '/favicon.ico',
    primaryColor: tenant.primaryColor,
    domain: hostname,
  }

  return (
    <TenantContext.Provider value={contextValue}>
      {children}
    </TenantContext.Provider>
  )
}
